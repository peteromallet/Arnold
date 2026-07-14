"""Focused tests for ticket–epic relationship normalization, legacy compatibility,
store replay, and the rule that epic completion addresses only resolving links.

Covers T5 requirements:
- Relationship normalization (parse_frontmatter_links)
- Legacy epics frontmatter compatibility (no kind/provenance keys)
- Store replay compatibility (idempotency)
- Auto-address gated only by resolves_on_complete (auto_address_predicate)
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.schemas import TicketEpicLink
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.store import (
    FileStore,
    deterministic_idempotency_key,
)
from arnold_pipelines.megaplan.tickets.relationships import (
    KIND_ASSOCIATED,
    KIND_PROMOTED_TO_EPIC,
    KIND_RESOLVES_ON_COMPLETE,
    RELATIONSHIP_KINDS,
    auto_address_predicate,
    parse_frontmatter_links,
    serialize_links_to_frontmatter,
)
from arnold_pipelines.megaplan.tickets.promotion import promote_ticket

idem = deterministic_idempotency_key


# ---------------------------------------------------------------------------
# Relationship kind constants
# ---------------------------------------------------------------------------


def test_relationship_kinds_frozenset() -> None:
    """The recognised kinds frozenset must include the three canonical kinds."""
    assert KIND_ASSOCIATED in RELATIONSHIP_KINDS
    assert KIND_PROMOTED_TO_EPIC in RELATIONSHIP_KINDS
    assert KIND_RESOLVES_ON_COMPLETE in RELATIONSHIP_KINDS
    assert len(RELATIONSHIP_KINDS) == 3


# ---------------------------------------------------------------------------
# parse_frontmatter_links — normalisation
# ---------------------------------------------------------------------------


def test_parse_legacy_entry_with_resolves_on_complete_true() -> None:
    """Legacy entry (no kind/provenance) with resolves_on_complete=True
    normalises to kind='resolves_on_complete'."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {"epic_id": "epic-1", "resolves_on_complete": True},
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    assert len(links) == 1
    assert links[0].epic_id == "epic-1"
    assert links[0].resolves_on_complete is True
    assert links[0].kind == KIND_RESOLVES_ON_COMPLETE
    assert links[0].provenance is None


def test_parse_legacy_entry_with_resolves_on_complete_false() -> None:
    """Legacy entry (no kind/provenance) with resolves_on_complete=False
    normalises to kind='associated'."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {"epic_id": "epic-2", "resolves_on_complete": False},
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    assert len(links) == 1
    assert links[0].epic_id == "epic-2"
    assert links[0].resolves_on_complete is False
    assert links[0].kind == KIND_ASSOCIATED
    assert links[0].provenance is None


def test_parse_legacy_entry_missing_resolves_on_complete() -> None:
    """Legacy entry without resolves_on_complete key defaults to associated."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {"epic_id": "epic-3"},
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    assert len(links) == 1
    assert links[0].epic_id == "epic-3"
    assert links[0].resolves_on_complete is False
    assert links[0].kind == KIND_ASSOCIATED


def test_parse_new_style_entry_preserves_kind_and_provenance() -> None:
    """New-style entries with explicit kind and provenance are preserved."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {
                "epic_id": "epic-4",
                "resolves_on_complete": True,
                "kind": KIND_PROMOTED_TO_EPIC,
                "provenance": "promotion/2026-07",
            },
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    assert len(links) == 1
    assert links[0].epic_id == "epic-4"
    assert links[0].kind == KIND_PROMOTED_TO_EPIC
    assert links[0].provenance == "promotion/2026-07"
    # resolves_on_complete preserved as-is
    assert links[0].resolves_on_complete is True


def test_parse_new_style_associated_with_provenance() -> None:
    """New-style associated entry with provenance is preserved."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {
                "epic_id": "epic-5",
                "resolves_on_complete": False,
                "kind": KIND_ASSOCIATED,
                "provenance": "manual/2026",
            },
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    assert links[0].kind == KIND_ASSOCIATED
    assert links[0].provenance == "manual/2026"


def test_parse_multiple_entries_mixed_legacy_and_new() -> None:
    """Mixed legacy and new-style entries are all normalized correctly."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {"epic_id": "epic-legacy", "resolves_on_complete": True},
            {
                "epic_id": "epic-new",
                "resolves_on_complete": False,
                "kind": KIND_PROMOTED_TO_EPIC,
                "provenance": "promotion",
            },
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    assert len(links) == 2

    legacy = next(link for link in links if link.epic_id == "epic-legacy")
    assert legacy.kind == KIND_RESOLVES_ON_COMPLETE
    assert legacy.provenance is None

    new_style = next(link for link in links if link.epic_id == "epic-new")
    assert new_style.kind == KIND_PROMOTED_TO_EPIC
    assert new_style.provenance == "promotion"


def test_parse_empty_epics() -> None:
    """Empty or missing epics list returns empty list."""
    assert parse_frontmatter_links({}, ticket_id="tid") == []
    assert parse_frontmatter_links({"epics": []}, ticket_id="tid") == []
    assert parse_frontmatter_links({"epics": None}, ticket_id="tid") == []


def test_parse_skips_invalid_entries() -> None:
    """Non-dict entries and entries without epic_id are skipped."""
    record = {
        "id": "01J1234567890",
        "epics": [
            "not-a-dict",
            {"resolves_on_complete": True},  # no epic_id
            {"epic_id": None},
            {"epic_id": ""},
            {"epic_id": "epic-valid", "resolves_on_complete": True},
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    assert len(links) == 1
    assert links[0].epic_id == "epic-valid"


def test_parse_unknown_kind_string_falls_back_to_resolves_based_normalisation() -> None:
    """An unrecognised kind string does not prevent normalisation —
    it falls back to the resolves_on_complete-based inference."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {
                "epic_id": "epic-unk",
                "resolves_on_complete": True,
                "kind": "some-unknown-kind",
            },
        ],
    }
    links = parse_frontmatter_links(record, ticket_id="01J1234567890")
    # Since the kind is not in RELATIONSHIP_KINDS, we fall back to
    # resolves_on_complete → resolves_on_complete
    assert links[0].kind == KIND_RESOLVES_ON_COMPLETE


# ---------------------------------------------------------------------------
# serialize_links_to_frontmatter — round-trip
# ---------------------------------------------------------------------------


def test_serialize_always_emits_kind_and_provenance() -> None:
    """Every serialized entry includes kind and provenance keys."""
    links = [
        TicketEpicLink(
            ticket_id="tid",
            epic_id="epic-1",
            resolves_on_complete=True,
            kind=KIND_RESOLVES_ON_COMPLETE,
            provenance=None,
        ),
        TicketEpicLink(
            ticket_id="tid",
            epic_id="epic-2",
            resolves_on_complete=False,
            kind=KIND_ASSOCIATED,
            provenance="manual",
        ),
    ]
    serialized = serialize_links_to_frontmatter(links)
    assert len(serialized) == 2
    for entry in serialized:
        assert "kind" in entry
        assert "provenance" in entry
        assert "epic_id" in entry
        assert "resolves_on_complete" in entry
        assert "linked_at" in entry


def test_parse_serialize_round_trip_is_idempotent() -> None:
    """Parse → serialize → re-parse round-trip is idempotent."""
    record = {
        "id": "01J1234567890",
        "epics": [
            {"epic_id": "epic-a", "resolves_on_complete": True},
            {
                "epic_id": "epic-b",
                "resolves_on_complete": False,
                "kind": KIND_PROMOTED_TO_EPIC,
                "provenance": "promotion",
            },
        ],
    }
    # First parse
    links_1 = parse_frontmatter_links(record, ticket_id="01J1234567890")
    serialized = serialize_links_to_frontmatter(links_1)

    # Second parse from serialized
    reconstituted_record = {"id": "01J1234567890", "epics": serialized}
    links_2 = parse_frontmatter_links(reconstituted_record, ticket_id="01J1234567890")

    assert len(links_1) == len(links_2)
    for l1, l2 in zip(sorted(links_1, key=lambda l: l.epic_id), sorted(links_2, key=lambda l: l.epic_id)):
        assert l1.epic_id == l2.epic_id
        assert l1.resolves_on_complete == l2.resolves_on_complete
        assert l1.kind == l2.kind
        assert l1.provenance == l2.provenance


def test_serialize_round_trip_preserves_promoted_to_epic() -> None:
    """A promoted_to_epic link survives the round-trip with kind intact."""
    links = [
        TicketEpicLink(
            ticket_id="tid",
            epic_id="epic-promo",
            resolves_on_complete=False,
            kind=KIND_PROMOTED_TO_EPIC,
            provenance="roadmap-2026",
        ),
    ]
    serialized = serialize_links_to_frontmatter(links)
    reconstituted = parse_frontmatter_links(
        {"id": "tid", "epics": serialized}, ticket_id="tid",
    )
    assert reconstituted[0].kind == KIND_PROMOTED_TO_EPIC
    assert reconstituted[0].provenance == "roadmap-2026"


# ---------------------------------------------------------------------------
# auto_address_predicate
# ---------------------------------------------------------------------------


def test_auto_address_predicate_true_only_for_resolves_on_complete() -> None:
    """Predicate returns True only when resolves_on_complete is True."""
    resolving = TicketEpicLink(
        ticket_id="tid",
        epic_id="epic-r",
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
    )
    associated = TicketEpicLink(
        ticket_id="tid",
        epic_id="epic-a",
        resolves_on_complete=False,
        kind=KIND_ASSOCIATED,
    )
    promoted = TicketEpicLink(
        ticket_id="tid",
        epic_id="epic-p",
        resolves_on_complete=False,
        kind=KIND_PROMOTED_TO_EPIC,
    )

    assert auto_address_predicate(resolving) is True
    assert auto_address_predicate(associated) is False
    assert auto_address_predicate(promoted) is False


def test_auto_address_predicate_does_not_gate_on_kind() -> None:
    """Auto-address only consults resolves_on_complete, never kind.
    Even a legacy-normalised 'associated' link triggers auto-address
    if resolves_on_complete=True."""
    # Edge case: kind=associated but resolves_on_complete=True
    # (shouldn't happen in new writes, but legacy could produce this)
    odd_link = TicketEpicLink(
        ticket_id="tid",
        epic_id="epic-x",
        resolves_on_complete=True,
        kind=KIND_ASSOCIATED,
    )
    assert auto_address_predicate(odd_link) is True

    # Conversely: kind=resolves_on_complete but resolves=False
    odd_link2 = TicketEpicLink(
        ticket_id="tid",
        epic_id="epic-y",
        resolves_on_complete=False,
        kind=KIND_RESOLVES_ON_COMPLETE,
    )
    assert auto_address_predicate(odd_link2) is False


# ---------------------------------------------------------------------------
# FileStore integration — legacy frontmatter compatibility
# ---------------------------------------------------------------------------


@pytest.fixture
def file_store(tmp_path: Path) -> FileStore:
    """A FileStore rooted in a temporary directory with a minimal git repo."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir(parents=True)

    # Initialize a real git repo with an initial commit
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo, check=True, capture_output=True,
    )
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=repo, check=True, capture_output=True,
    )

    # Store dir
    store_dir = repo / ".megaplan" / "store"
    store_dir.mkdir(parents=True)
    return FileStore(root=store_dir, repo_root=repo)


def _make_ticket(store: FileStore, title: str, ticket_id: str = "01JTEST001") -> None:
    """Create a ticket through the store for integration tests."""
    codebase = store._resolve_ticket_codebase()
    store.create_ticket(
        codebase_id=codebase.id,
        title=title,
        body="Test body",
        slug=title.lower().replace(" ", "-"),
        ticket_id=ticket_id,
    )


def test_legacy_frontmatter_without_kind_is_normalised_on_read(
    file_store: FileStore,
) -> None:
    """A ticket file written with legacy epics frontmatter (no kind/provenance)
    is normalised when read back through the store."""
    _make_ticket(file_store, "Legacy Ticket", "01JTEST001")
    codebase = file_store._resolve_ticket_codebase()

    # Manually write legacy-style frontmatter (no kind/provenance)
    from arnold_pipelines.megaplan.tickets.files import read_ticket_file, write_ticket_file

    ticket_path = None
    for p, rec in file_store._ticket_file_records():
        if rec.get("id") == "01JTEST001":
            ticket_path = p
            break
    assert ticket_path is not None

    record = read_ticket_file(ticket_path)
    assert record is not None
    record["epics"] = [
        {"epic_id": "epic-legacy-a", "resolves_on_complete": True},
        {"epic_id": "epic-legacy-b", "resolves_on_complete": False},
    ]
    write_ticket_file(ticket_path, record)

    # Read back through store — should normalise
    links = file_store.list_ticket_epic_links(ticket_id="01JTEST001")
    assert len(links) == 2

    link_a = next(link for link in links if link.epic_id == "epic-legacy-a")
    assert link_a.kind == KIND_RESOLVES_ON_COMPLETE
    assert link_a.provenance is None

    link_b = next(link for link in links if link.epic_id == "epic-legacy-b")
    assert link_b.kind == KIND_ASSOCIATED
    assert link_b.provenance is None


def test_legacy_frontmatter_round_trips_with_kind_added(
    file_store: FileStore,
) -> None:
    """After reading legacy frontmatter, writing back adds kind/provenance."""
    _make_ticket(file_store, "Roundtrip Ticket", "01JTEST002")

    from arnold_pipelines.megaplan.tickets.files import read_ticket_file, write_ticket_file

    ticket_path = None
    for p, rec in file_store._ticket_file_records():
        if rec.get("id") == "01JTEST002":
            ticket_path = p
            break
    assert ticket_path is not None

    # Write legacy entry
    record = read_ticket_file(ticket_path)
    assert record is not None
    record["epics"] = [{"epic_id": "epic-rt", "resolves_on_complete": True}]
    write_ticket_file(ticket_path, record)

    # Link through store (which reads legacy, normalises, writes back)
    file_store.link_ticket_to_epic(
        ticket_id="01JTEST002",
        epic_id="epic-rt-2",
        resolves_on_complete=False,
        kind=KIND_ASSOCIATED,
        provenance="test",
    )

    # Re-read the file to verify kind/provenance are now present
    record2 = read_ticket_file(ticket_path)
    assert record2 is not None
    epics = record2.get("epics", [])
    assert len(epics) == 2
    for entry in epics:
        assert "kind" in entry, f"Missing kind in {entry}"
        assert "provenance" in entry, f"Missing provenance in {entry}"


def test_promote_ticket_end_to_end_is_idempotent(
    file_store: FileStore,
) -> None:
    """Promotion creates a distinct epic, records provenance, and replays cleanly."""
    from arnold_pipelines.megaplan.tickets.core import new
    from arnold_pipelines.megaplan.tickets.files import read_ticket_file

    repo_root = Path(file_store.repo_root)
    ticket_id = new(
        "Promote Me",
        body="Ticket body",
        store=file_store,
        cwd=repo_root,
    )

    first = promote_ticket(ticket_id, store=file_store, cwd=repo_root)
    second = promote_ticket(ticket_id, store=file_store, cwd=repo_root)

    assert ticket_id != first.epic.id
    assert first.epic.id == "promote-me"
    assert second.epic.id == first.epic.id
    assert first.initiative_slug == "promote-me"
    assert second.initiative_created is False
    assert second.epic_created is False

    links = file_store.list_ticket_epic_links(ticket_id=ticket_id, epic_id=first.epic.id)
    assert len(links) == 1
    assert links[0].kind == KIND_PROMOTED_TO_EPIC
    assert links[0].provenance == f"promotion:{ticket_id}"
    assert links[0].resolves_on_complete is True

    ticket_path = next(
        path for path, record in file_store._ticket_file_records() if record.get("id") == ticket_id
    )
    record = read_ticket_file(ticket_path)
    assert record is not None
    parsed_links = parse_frontmatter_links(record, ticket_id=ticket_id)
    assert len(parsed_links) == 1
    assert parsed_links[0].epic_id == first.epic.id
    assert parsed_links[0].kind == KIND_PROMOTED_TO_EPIC


# ---------------------------------------------------------------------------
# FileStore integration — auto-address gating
# ---------------------------------------------------------------------------


def test_address_tickets_resolved_by_epic_only_addresses_resolving_links(
    file_store: FileStore,
) -> None:
    """Only tickets with resolves_on_complete=True are auto-addressed
    when an epic completes."""
    _make_ticket(file_store, "Resolving Ticket", "01JTEST-RESOLVE")
    _make_ticket(file_store, "Associated Ticket", "01JTEST-ASSOC")
    codebase = file_store._resolve_ticket_codebase()

    # Create two epics
    epic = file_store.create_epic(
        title="Auto-Address Epic",
        goal="Test auto-address gating",
        body="# Epic\n",
        idempotency_key=idem("test", "addr", "epic"),
    )

    # Link resolving ticket
    file_store.link_ticket_to_epic(
        ticket_id="01JTEST-RESOLVE",
        epic_id=epic.id,
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
    )

    # Link associated ticket (should NOT auto-address)
    file_store.link_ticket_to_epic(
        ticket_id="01JTEST-ASSOC",
        epic_id=epic.id,
        resolves_on_complete=False,
        kind=KIND_ASSOCIATED,
    )

    # Address tickets resolved by epic
    addressed = file_store.address_tickets_resolved_by_epic(epic.id)

    # Only the resolving ticket should be addressed
    assert addressed == ["01JTEST-RESOLVE"]

    resolving = file_store.load_ticket("01JTEST-RESOLVE")
    assert resolving is not None
    assert resolving.status == "addressed"

    associated = file_store.load_ticket("01JTEST-ASSOC")
    assert associated is not None
    assert associated.status == "open"  # NOT addressed


def test_legacy_resolves_on_complete_still_triggers_auto_address(
    file_store: FileStore,
) -> None:
    """A ticket linked via legacy frontmatter (no kind) with
    resolves_on_complete=True still auto-addresses on epic completion."""
    _make_ticket(file_store, "Legacy Resolve Ticket", "01JTEST-LEGACY")

    from arnold_pipelines.megaplan.tickets.files import read_ticket_file, write_ticket_file

    ticket_path = None
    for p, rec in file_store._ticket_file_records():
        if rec.get("id") == "01JTEST-LEGACY":
            ticket_path = p
            break
    assert ticket_path is not None

    epic = file_store.create_epic(
        title="Legacy Auto-Address Epic",
        goal="Test legacy auto-address",
        body="# Epic\n",
        idempotency_key=idem("test", "legacy-addr", "epic"),
    )

    # Write legacy-style link (no kind/provenance)
    record = read_ticket_file(ticket_path)
    assert record is not None
    record["epics"] = [{"epic_id": epic.id, "resolves_on_complete": True}]
    write_ticket_file(ticket_path, record)

    addressed = file_store.address_tickets_resolved_by_epic(epic.id)
    assert addressed == ["01JTEST-LEGACY"]

    ticket = file_store.load_ticket("01JTEST-LEGACY")
    assert ticket is not None
    assert ticket.status == "addressed"


def test_address_tickets_skips_already_addressed_tickets(
    file_store: FileStore,
) -> None:
    """address_tickets_resolved_by_epic skips tickets that are already
    addressed (not open)."""
    _make_ticket(file_store, "Already Addressed", "01JTEST-ALREADY")
    codebase = file_store._resolve_ticket_codebase()

    epic = file_store.create_epic(
        title="Skip Addressed Epic",
        goal="Test skip already addressed",
        body="# Epic\n",
        idempotency_key=idem("test", "skip-addr", "epic"),
    )

    file_store.link_ticket_to_epic(
        ticket_id="01JTEST-ALREADY",
        epic_id=epic.id,
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
    )

    # Manually set the ticket to addressed first
    file_store.update_ticket("01JTEST-ALREADY", status="addressed")

    addressed = file_store.address_tickets_resolved_by_epic(epic.id)
    assert addressed == []  # No open tickets to address


def test_address_tickets_returns_empty_for_no_links(
    file_store: FileStore,
) -> None:
    """address_tickets_resolved_by_epic returns empty list when no links exist."""
    epic = file_store.create_epic(
        title="Isolated Epic",
        goal="Test no links",
        body="# Epic\n",
        idempotency_key=idem("test", "no-links", "epic"),
    )
    addressed = file_store.address_tickets_resolved_by_epic(epic.id)
    assert addressed == []


# ---------------------------------------------------------------------------
# FileStore integration — store replay / idempotency
# ---------------------------------------------------------------------------


def test_link_ticket_to_epic_idempotency(
    file_store: FileStore,
) -> None:
    """Replaying link_ticket_to_epic with the same idempotency_key
    returns the original link without altering data."""
    _make_ticket(file_store, "Idempotent Link", "01JTEST-IDEM")
    epic = file_store.create_epic(
        title="Idempotent Epic",
        goal="Test idempotent link",
        body="# Epic\n",
        idempotency_key=idem("test", "idem-link", "epic"),
    )

    key = idem("test", "idem-link", "link")
    link1 = file_store.link_ticket_to_epic(
        ticket_id="01JTEST-IDEM",
        epic_id=epic.id,
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
        provenance="test-replay",
        idempotency_key=key,
    )
    link2 = file_store.link_ticket_to_epic(
        ticket_id="01JTEST-IDEM",
        epic_id=epic.id,
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
        provenance="test-replay",
        idempotency_key=key,
    )
    assert link1.ticket_id == link2.ticket_id
    assert link1.epic_id == link2.epic_id
    assert link1.linked_at == link2.linked_at

    # Only one link exists
    links = file_store.list_ticket_epic_links(ticket_id="01JTEST-IDEM")
    assert len(links) == 1


def test_unlink_ticket_from_epic_idempotency(
    file_store: FileStore,
) -> None:
    """Replaying unlink_ticket_from_epic with the same idempotency_key
    is idempotent — unlinking an already-unlinked ticket succeeds."""
    _make_ticket(file_store, "Idempotent Unlink", "01JTEST-UNLINK")
    epic = file_store.create_epic(
        title="Unlink Idempotent Epic",
        goal="Test idempotent unlink",
        body="# Epic\n",
        idempotency_key=idem("test", "idem-unlink", "epic"),
    )
    file_store.link_ticket_to_epic(
        ticket_id="01JTEST-UNLINK",
        epic_id=epic.id,
        resolves_on_complete=False,
        kind=KIND_ASSOCIATED,
    )

    key = idem("test", "idem-unlink", "unlink")
    file_store.unlink_ticket_from_epic(
        ticket_id="01JTEST-UNLINK",
        epic_id=epic.id,
        idempotency_key=key,
    )
    # Second unlink should not raise
    file_store.unlink_ticket_from_epic(
        ticket_id="01JTEST-UNLINK",
        epic_id=epic.id,
        idempotency_key=key,
    )
    links = file_store.list_ticket_epic_links(ticket_id="01JTEST-UNLINK")
    assert links == []


def test_store_replay_does_not_fork_links(
    file_store: FileStore,
) -> None:
    """Linking then re-linking with different idempotency_key updates
    the existing link (same epic_id) rather than creating duplicates."""
    _make_ticket(file_store, "Replay No Fork", "01JTEST-FORK")
    epic = file_store.create_epic(
        title="Fork Test Epic",
        goal="Test no fork on replay",
        body="# Epic\n",
        idempotency_key=idem("test", "fork", "epic"),
    )

    link = file_store.link_ticket_to_epic(
        ticket_id="01JTEST-FORK",
        epic_id=epic.id,
        resolves_on_complete=False,
        kind=KIND_ASSOCIATED,
        provenance="first",
    )
    # Re-link same epic with new provenance
    link2 = file_store.link_ticket_to_epic(
        ticket_id="01JTEST-FORK",
        epic_id=epic.id,
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
        provenance="second",
    )
    # Should update, not create a second link for same epic
    links = file_store.list_ticket_epic_links(ticket_id="01JTEST-FORK")
    assert len(links) == 1
    assert links[0].kind == KIND_RESOLVES_ON_COMPLETE
    assert links[0].provenance == "second"
    # Newer link keeps newer linked_at but original linked_at is preserved
    assert links[0].linked_at == link.linked_at
