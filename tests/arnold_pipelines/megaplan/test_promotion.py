"""Promotion integration tests covering the full ticket→epic promotion lifecycle.

Covers T9 requirements:
- Tickets outside strategy (no forced visibility)
- Tickets in each horizon (Now, Next, Later roadmap replacement)
- Roadmap replacement semantics
- Retry / idempotency
- Conflict reporting for mismatched artifacts
- Source ticket retention
- Distinct epic identity (initiative slug, never ticket ULID)
- File / store relationship reconciliation
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.schemas import TicketEpicLink
from arnold_pipelines.megaplan.store import FileStore
from arnold_pipelines.megaplan.store.base import Store
from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    RoadmapHorizon,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)
from arnold_pipelines.megaplan.tickets.promotion import (
    PROVENANCE_PROMOTION,
    PromotionConflictError,
    TicketNotFoundError,
    promote_ticket,
)
from arnold_pipelines.megaplan.tickets.relationships import (
    KIND_PROMOTED_TO_EPIC,
    parse_frontmatter_links,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def promo_repo(tmp_path: Path):
    """Create a temporary git repo with a FileStore, tickets dir, and STRATEGY.md helpers."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)

    # Init git
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Store dir
    store_dir = repo / ".megaplan" / "store"
    store_dir.mkdir(parents=True)
    store = FileStore(root=store_dir, repo_root=repo)

    class RepoContext:
        """Provides helpers scoped to this repo."""

        def __init__(self, root: Path, store_: FileStore):
            self.root = root
            self.store = store_

        def create_ticket(self, title: str, ticket_id: str) -> str:
            """Create a ticket and return its id."""
            from arnold_pipelines.megaplan.tickets.files import (
                ticket_file_path,
                write_ticket_file,
            )
            from arnold_pipelines.megaplan.schemas.base import utc_now

            slug = title.lower().replace(" ", "-")
            fpath = ticket_file_path(str(self.root), ticket_id, slug)
            fpath.parent.mkdir(parents=True, exist_ok=True)
            now = utc_now()
            record = {
                "id": ticket_id,
                "title": title,
                "status": "open",
                "source": "human",
                "tags": [],
                "filed_by_actor_id": None,
                "filed_in_turn_id": None,
                "codebase_id": "test/test",
                "created_at": now,
                "last_edited_at": now,
                "resolution_note": None,
                "addressed_at": None,
                "epics": [],
                "__body__": f"Body of {title}",
            }
            write_ticket_file(fpath, record)
            return ticket_id

        def write_strategy(
            self,
            entries_by_horizon: dict[str, list[tuple[str, str, str]]] | None = None,
            *,
            ticket_in_horizon: str | None = None,
            ticket_id: str = "",
            ticket_title: str = "",
            epic_in_horizon: str | None = None,
            epic_ref: str = "",
            epic_title: str = "",
        ) -> Path:
            """Write a STRATEGY.md with optional roadmap entries.

            ``entries_by_horizon`` is a dict of horizon → list of (type, ref, display_title).
            As a convenience, ``ticket_in_horizon`` / ``epic_in_horizon`` can be used
            for single-entry setups.
            """
            entries: dict[str, list[tuple[str, str, str]]] = {
                "Now": [],
                "Next": [],
                "Later": [],
            }
            if entries_by_horizon:
                for h, items in entries_by_horizon.items():
                    entries[h] = list(items)

            if ticket_in_horizon and ticket_id:
                entries.setdefault(ticket_in_horizon, []).append(
                    ("ticket", ticket_id, ticket_title or ticket_id)
                )
            if epic_in_horizon and epic_ref:
                entries.setdefault(epic_in_horizon, []).append(
                    ("epic", epic_ref, epic_title or epic_ref)
                )

            return self._write_strategy_file(entries)

        def _write_strategy_file(
            self, roadmap_entries: dict[str, list[tuple[str, str, str]]]
        ) -> Path:
            content = self._build_strategy_content(roadmap_entries)
            spath = self.root / ".megaplan" / "STRATEGY.md"
            spath.parent.mkdir(parents=True, exist_ok=True)
            spath.write_text(content, encoding="utf-8")
            return spath

        def _build_strategy_content(
            self, roadmap_entries: dict[str, list[tuple[str, str, str]]]
        ) -> str:
            parts: list[str] = []
            parts.append("---")
            parts.append("schema_version: megaplan-strategy-v1")
            parts.append("---")
            parts.append("")
            for section_title in (
                "Mission",
                "Principles",
                "Architecture Direction",
                "Constraints",
                "Non-Goals",
            ):
                parts.append(f"## {section_title}")
                parts.append("")
                parts.append(f"Test {section_title.lower()} content.")
                parts.append("")
            for horizon in ("Now", "Next", "Later"):
                parts.append(f"## {horizon}")
                parts.append("")
                for type_, ref, display in roadmap_entries.get(horizon, []):
                    parts.append(f"- [{type_}:{ref}] {display}")
                parts.append("")
            return "\n".join(parts) + "\n"

        def read_strategy_content(self) -> str:
            spath = self.root / ".megaplan" / "STRATEGY.md"
            return spath.read_text(encoding="utf-8")

        def strategy_file_exists(self) -> bool:
            return (self.root / ".megaplan" / "STRATEGY.md").exists()

        def initiative_exists(self, slug: str) -> bool:
            from arnold_pipelines.megaplan.layout import initiative_root

            return initiative_root(str(self.root), slug).exists()

        def ticket_file_exists(self, ticket_id: str) -> bool:
            from arnold_pipelines.megaplan.tickets.files import iterate_ticket_files

            for _path, fm in iterate_ticket_files(str(self.root)):
                if fm.get("id") == ticket_id:
                    return True
            return False

        def read_ticket_frontmatter(self, ticket_id: str) -> dict[str, Any] | None:
            from arnold_pipelines.megaplan.tickets.files import iterate_ticket_files

            for _path, fm in iterate_ticket_files(str(self.root)):
                if fm.get("id") == ticket_id:
                    return fm
            return None

    ctx = RepoContext(repo, store)
    return ctx


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _links_for_ticket(store: FileStore, ticket_id: str) -> list[TicketEpicLink]:
    """Return all TicketEpicLink rows for a ticket."""
    return store.list_ticket_epic_links(ticket_id=ticket_id)


# ===========================================================================
# 1. Distinct Epic Identity
# ===========================================================================


class TestPromotionIdentity:
    """Epic ID is the initiative slug, never the ticket ULID."""

    def test_epic_id_is_initiative_slug_not_ticket_ulid(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Authentication Overhaul", "01JNX0000001")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        # The ticket ID is a ULID; the epic ID is a slug
        assert result.ticket_id == ticket_id
        assert result.epic.id != ticket_id
        assert result.epic.id == "authentication-overhaul"
        assert result.initiative_slug == "authentication-overhaul"

    def test_explicit_initiative_slug_used_as_epic_id(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Some Random Title", "01JNX0000002")
        result = promote_ticket(
            ticket_id,
            initiative_slug="custom-slug",
            store=store,
            cwd=ctx.root,
        )

        assert result.epic.id == "custom-slug"
        assert result.initiative_slug == "custom-slug"

    def test_epic_id_never_matches_ticket_ulid_pattern(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Unique Feature", "01JNX0000003")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        # Epic ID is a slug, not the ticket ID
        assert result.epic.id == "unique-feature"
        assert result.epic.id != ticket_id
        # Epic ID is lowercase kebab-case, never the ticket ULID format
        assert result.epic.id == result.epic.id.lower()
        assert " " not in result.epic.id


# ===========================================================================
# 2. Source Ticket Retention
# ===========================================================================


class TestPromotionTicketRetention:
    """The source ticket file is retained — never deleted — after promotion."""

    def test_ticket_file_exists_after_promotion(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Retain Me", "01JNX0000010")
        assert ctx.ticket_file_exists(ticket_id)

        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert ctx.ticket_file_exists(ticket_id), (
            "Ticket file must still exist after promotion"
        )

    def test_ticket_title_unchanged_after_promotion(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Original Title", "01JNX0000011")

        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        fm = ctx.read_ticket_frontmatter(ticket_id)
        assert fm is not None
        assert fm.get("title") == "Original Title"

    def test_ticket_status_unchanged_after_promotion(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Still Open", "01JNX0000012")

        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        fm = ctx.read_ticket_frontmatter(ticket_id)
        assert fm is not None
        assert fm.get("status") == "open"

    def test_ticket_id_field_unchanged_after_promotion(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("ID Check", "01JNX0000013")

        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        fm = ctx.read_ticket_frontmatter(ticket_id)
        assert fm is not None
        assert fm.get("id") == ticket_id

    def test_ticket_body_unchanged_after_promotion(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Body Check", "01JNX0000014")

        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        fm = ctx.read_ticket_frontmatter(ticket_id)
        assert fm is not None
        body = fm.get("__body__", "")
        assert "Body of Body Check" in str(body)


# ===========================================================================
# 3. Link Provenance
# ===========================================================================


class TestPromotionLinkProvenance:
    """The promoted_to_epic link has correct kind and provenance."""

    def test_link_kind_is_promoted_to_epic(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Link Kind", "01JNX0000020")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.link is not None
        assert result.link.kind == KIND_PROMOTED_TO_EPIC

    def test_link_provenance_includes_ticket_id(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Provenance Test", "01JNX0000021")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.link is not None
        assert result.link.provenance == f"{PROVENANCE_PROMOTION}:{ticket_id}"
        assert ticket_id in result.link.provenance

    def test_link_resolves_on_complete_defaults_true(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Resolving Default", "01JNX0000022")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.link is not None
        assert result.link.resolves_on_complete is True

    def test_link_resolves_on_complete_false_when_requested(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Non-resolving", "01JNX0000023")
        result = promote_ticket(
            ticket_id,
            store=store,
            cwd=ctx.root,
            resolves_on_complete=False,
        )

        assert result.link is not None
        assert result.link.resolves_on_complete is False


# ===========================================================================
# 4. Tickets Outside Strategy (no forced visibility)
# ===========================================================================


class TestPromotionStrategyOutside:
    """Non-roadmap tickets promote without being forced into the strategy."""

    def test_no_strategy_file_promotes_without_error(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        # No STRATEGY.md exists
        assert not ctx.strategy_file_exists()

        ticket_id = ctx.create_ticket("No Strategy Ticket", "01JNX0000030")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.strategy_updated is False
        assert result.epic.id == "no-strategy-ticket"

    def test_skip_strategy_flag_skips_strategy_even_when_file_exists(
        self, promo_repo
    ) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(ticket_in_horizon="Now", ticket_id="01JNX0000031",
                           ticket_title="Skip Me")
        ticket_id = ctx.create_ticket("Skip Me", "01JNX0000031")

        result = promote_ticket(
            ticket_id, store=store, cwd=ctx.root, skip_strategy=True
        )

        assert result.strategy_updated is False

    def test_non_roadmap_ticket_not_forced_into_strategy(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        # Strategy exists but has NO ticket entry for this ticket
        ctx.write_strategy()  # empty roadmap

        ticket_id = ctx.create_ticket("Not In Roadmap", "01JNX0000032")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.strategy_updated is True
        content = ctx.read_strategy_content()
        # Ticket ref should NOT appear in the strategy (no forced visibility)
        assert ticket_id not in content, (
            "Ticket ULID must not be forced into strategy"
        )
        # Epic should be present
        assert "not-in-roadmap" in content

    def test_non_roadmap_ticket_epic_defaults_to_next(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy()  # empty roadmap, ticket not present

        ticket_id = ctx.create_ticket("Default Next", "01JNX0000033")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.strategy_updated is True
        content = ctx.read_strategy_content()
        # The epic should appear in the "Next" horizon (default for non-roadmap)
        # Verify by parsing
        from arnold_pipelines.megaplan.strategy import parse_strategy

        doc = parse_strategy(content, "STRATEGY.md")
        next_entries = [
            e for e in doc.roadmap.get("Next", []) if e.identity.ref == "default-next"
        ]
        assert len(next_entries) == 1
        assert next_entries[0].identity.type == "epic"


# ===========================================================================
# 5. Tickets in Each Horizon (roadmap replacement)
# ===========================================================================


class TestPromotionStrategyHorizons:
    """Tickets in Now, Next, Later are replaced with epic entries in the same horizon."""

    def test_ticket_in_now_replaced_by_epic_in_now(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(
            ticket_in_horizon="Now",
            ticket_id="01JNX0000040",
            ticket_title="Now Ticket",
        )
        ticket_id = ctx.create_ticket("Now Ticket", "01JNX0000040")

        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.strategy_updated is True

        from arnold_pipelines.megaplan.strategy import parse_strategy

        content = ctx.read_strategy_content()
        doc = parse_strategy(content, "STRATEGY.md")

        # Ticket removed from Now
        ticket_now = [
            e
            for e in doc.roadmap.get("Now", [])
            if e.identity.ref == ticket_id
        ]
        assert ticket_now == []

        # Epic in Now
        epic_now = [
            e
            for e in doc.roadmap.get("Now", [])
            if e.identity.ref == "now-ticket"
        ]
        assert len(epic_now) == 1
        assert epic_now[0].identity.type == "epic"

    def test_ticket_in_next_replaced_by_epic_in_next(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(
            ticket_in_horizon="Next",
            ticket_id="01JNX0000041",
            ticket_title="Next Ticket",
        )
        ticket_id = ctx.create_ticket("Next Ticket", "01JNX0000041")

        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        from arnold_pipelines.megaplan.strategy import parse_strategy

        content = ctx.read_strategy_content()
        doc = parse_strategy(content, "STRATEGY.md")

        assert result.strategy_updated is True
        next_epic = [
            e
            for e in doc.roadmap.get("Next", [])
            if e.identity.ref == "next-ticket"
        ]
        assert len(next_epic) == 1
        assert next_epic[0].identity.type == "epic"

        # Ticket removed
        ticket_entries = [
            e
            for entries in doc.roadmap.values()
            for e in entries
            if e.identity.ref == ticket_id
        ]
        assert ticket_entries == []

    def test_ticket_in_later_replaced_by_epic_in_later(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(
            ticket_in_horizon="Later",
            ticket_id="01JNX0000042",
            ticket_title="Later Ticket",
        )
        ticket_id = ctx.create_ticket("Later Ticket", "01JNX0000042")

        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        from arnold_pipelines.megaplan.strategy import parse_strategy

        content = ctx.read_strategy_content()
        doc = parse_strategy(content, "STRATEGY.md")

        assert result.strategy_updated is True
        later_epic = [
            e
            for e in doc.roadmap.get("Later", [])
            if e.identity.ref == "later-ticket"
        ]
        assert len(later_epic) == 1
        assert later_epic[0].identity.type == "epic"

    def test_explicit_horizon_overrides_ticket_horizon(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(
            ticket_in_horizon="Later",
            ticket_id="01JNX0000043",
            ticket_title="Move to Now",
        )
        ticket_id = ctx.create_ticket("Move to Now", "01JNX0000043")

        result = promote_ticket(
            ticket_id, store=store, cwd=ctx.root, horizon="Now"
        )

        from arnold_pipelines.megaplan.strategy import parse_strategy

        content = ctx.read_strategy_content()
        doc = parse_strategy(content, "STRATEGY.md")

        # Epic should be in Now (explicit), not Later
        now_epic = [
            e
            for e in doc.roadmap.get("Now", [])
            if e.identity.ref == "move-to-now"
        ]
        assert len(now_epic) == 1

        later_ticket = [
            e
            for e in doc.roadmap.get("Later", [])
            if e.identity.ref == ticket_id
        ]
        assert later_ticket == []

    def test_other_entries_preserved_during_promotion(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(
            entries_by_horizon={
                "Now": [
                    ("ticket", "01JNX0000044", "Promote Me"),
                    ("epic", "existing-epic", "Keep Me"),
                ],
                "Later": [("ticket", "other-ticket", "Stay Put")],
            }
        )
        ticket_id = ctx.create_ticket("Promote Me", "01JNX0000044")

        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        from arnold_pipelines.megaplan.strategy import parse_strategy

        content = ctx.read_strategy_content()
        doc = parse_strategy(content, "STRATEGY.md")

        # Existing epic preserved
        now_entries = doc.roadmap.get("Now", [])
        assert any(e.identity.ref == "existing-epic" for e in now_entries)

        # Other ticket in Later preserved
        later_entries = doc.roadmap.get("Later", [])
        assert any(e.identity.ref == "other-ticket" for e in later_entries)

        # Promoted ticket removed
        assert not any(
            e.identity.ref == ticket_id
            for entries in doc.roadmap.values()
            for e in entries
        )

        # Promoted epic present
        assert any(
            e.identity.ref == "promote-me" and e.identity.type == "epic"
            for e in now_entries
        )


# ===========================================================================
# 6. Idempotency (retry)
# ===========================================================================


class TestPromotionIdempotency:
    """Promoting the same ticket twice produces identical results — no duplicates."""

    def test_same_ticket_promoted_twice_same_epic_id(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Idempotent", "01JNX0000050")
        first = promote_ticket(ticket_id, store=store, cwd=ctx.root)
        second = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert first.epic.id == second.epic.id
        assert first.initiative_slug == second.initiative_slug

    def test_initiative_not_recreated_on_retry(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Initiative Once", "01JNX0000051")
        first = promote_ticket(ticket_id, store=store, cwd=ctx.root)
        assert first.initiative_created is True

        second = promote_ticket(ticket_id, store=store, cwd=ctx.root)
        assert second.initiative_created is False

    def test_epic_not_recreated_on_retry(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Epic Once", "01JNX0000052")
        first = promote_ticket(ticket_id, store=store, cwd=ctx.root)
        assert first.epic_created is True

        second = promote_ticket(ticket_id, store=store, cwd=ctx.root)
        assert second.epic_created is False

    def test_link_not_duplicated_on_retry(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Link Once", "01JNX0000053")
        promote_ticket(ticket_id, store=store, cwd=ctx.root)
        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        links = _links_for_ticket(store, ticket_id)
        promo_links = [
            link for link in links if link.kind == KIND_PROMOTED_TO_EPIC
        ]
        assert len(promo_links) == 1, "Must not create duplicate promoted_to_epic links"

    def test_strategy_not_doubly_mutated(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(
            ticket_in_horizon="Now",
            ticket_id="01JNX0000054",
            ticket_title="Once Mutated",
        )
        ticket_id = ctx.create_ticket("Once Mutated", "01JNX0000054")

        promote_ticket(ticket_id, store=store, cwd=ctx.root)
        content_after_first = ctx.read_strategy_content()

        promote_ticket(ticket_id, store=store, cwd=ctx.root)
        content_after_second = ctx.read_strategy_content()

        # The second promotion should not further change the strategy
        assert content_after_first == content_after_second, (
            "Strategy must be identical after idempotent retry"
        )

    def test_idempotency_with_explicit_idempotency_key(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Explicit Key", "01JNX0000055")
        first = promote_ticket(
            ticket_id,
            store=store,
            cwd=ctx.root,
            idempotency_key="explicit-key-001",
        )
        second = promote_ticket(
            ticket_id,
            store=store,
            cwd=ctx.root,
            idempotency_key="explicit-key-001",
        )

        assert first.epic.id == second.epic.id
        assert first.epic_created is True
        assert second.epic_created is False


# ===========================================================================
# 7. Conflict Reporting
# ===========================================================================


class TestPromotionConflicts:
    """Promotion raises precise conflicts for mismatched artifacts."""

    def test_already_promoted_to_different_epic_raises_conflict(
        self, promo_repo
    ) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Conflict Ticket", "01JNX0000060")

        # First promotion creates an epic with the derived slug
        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        # Second promotion to a different slug should fail
        with pytest.raises(PromotionConflictError) as exc_info:
            promote_ticket(
                ticket_id,
                initiative_slug="different-slug",
                store=store,
                cwd=ctx.root,
            )

        assert exc_info.value.conflict_type == "already_promoted_to_different_epic"
        assert ticket_id in str(exc_info.value)
        assert "different-slug" in str(exc_info.value)

    def test_already_promoted_conflict_includes_both_epic_ids(
        self, promo_repo
    ) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Both Epics", "01JNX0000061")
        promote_ticket(ticket_id, store=store, cwd=ctx.root)

        with pytest.raises(PromotionConflictError) as exc_info:
            promote_ticket(
                ticket_id,
                initiative_slug="other-epic",
                store=store,
                cwd=ctx.root,
            )

        details = exc_info.value.details
        assert details["ticket_id"] == ticket_id
        assert details["existing_epic_id"] == "both-epics"
        assert details["target_epic_id"] == "other-epic"

    def test_ticket_not_found_raises(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        with pytest.raises(TicketNotFoundError):
            promote_ticket(
                "nonexistent-ticket-id",
                store=store,
                cwd=ctx.root,
            )

    def test_ticket_not_found_message_includes_ticket_id(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        with pytest.raises(TicketNotFoundError) as exc_info:
            promote_ticket("01JNX9999999", store=store, cwd=ctx.root)

        assert "01JNX9999999" in str(exc_info.value)


# ===========================================================================
# 8. File / Store Relationship Reconciliation
# ===========================================================================


class TestPromotionFileStoreReconciliation:
    """Promotion links are recorded in both file frontmatter and store."""

    def test_link_recorded_in_file_frontmatter(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Frontmatter Link", "01JNX0000070")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        fm = ctx.read_ticket_frontmatter(ticket_id)
        assert fm is not None

        links = parse_frontmatter_links(fm, ticket_id=ticket_id)
        promo_links = [
            link for link in links if link.kind == KIND_PROMOTED_TO_EPIC
        ]
        assert len(promo_links) == 1
        assert promo_links[0].epic_id == result.epic.id

    def test_link_recorded_in_store(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Store Link", "01JNX0000071")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        links = _links_for_ticket(store, ticket_id)
        promo_links = [
            link for link in links if link.kind == KIND_PROMOTED_TO_EPIC
        ]
        assert len(promo_links) == 1
        assert promo_links[0].epic_id == result.epic.id

    def test_file_and_store_links_agree(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Agreement Link", "01JNX0000072")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        # File link
        fm = ctx.read_ticket_frontmatter(ticket_id)
        file_links = parse_frontmatter_links(fm, ticket_id=ticket_id)
        file_promo = [
            link for link in file_links if link.kind == KIND_PROMOTED_TO_EPIC
        ]

        # Store link
        store_links = _links_for_ticket(store, ticket_id)
        store_promo = [
            link for link in store_links if link.kind == KIND_PROMOTED_TO_EPIC
        ]

        assert len(file_promo) == 1
        assert len(store_promo) == 1
        assert file_promo[0].epic_id == store_promo[0].epic_id
        assert file_promo[0].ticket_id == store_promo[0].ticket_id
        assert file_promo[0].kind == store_promo[0].kind
        assert file_promo[0].provenance == store_promo[0].provenance
        assert (
            file_promo[0].resolves_on_complete == store_promo[0].resolves_on_complete
        )

    def test_epic_loadable_from_store_after_promotion(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Loadable Epic", "01JNX0000073")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        epic = store.load_epic(result.epic.id)
        assert epic is not None
        assert epic.id == result.epic.id
        assert epic.title == result.epic.title

    def test_epic_body_and_goal_populated_from_ticket(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Rich Ticket", "01JNX0000074")
        result = promote_ticket(
            ticket_id,
            store=store,
            cwd=ctx.root,
            epic_title="Rich Epic Title",
            epic_goal="Rich Epic Goal",
            epic_body="# Rich Body\n\nContent here.",
        )

        epic = store.load_epic(result.epic.id)
        assert epic is not None
        assert epic.title == "Rich Epic Title"
        assert epic.goal == "Rich Epic Goal"
        assert "Rich Body" in epic.body

    def test_initiative_folder_created(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Initiative Folder", "01JNX0000075")
        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.initiative_created is True
        assert ctx.initiative_exists(result.initiative_slug)

    def test_initiative_reused_when_already_exists(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ticket_id = ctx.create_ticket("Reuse Initiative", "01JNX0000076")

        # Create initiative folder manually first
        from arnold_pipelines.megaplan.layout import initiative_root

        init_root = initiative_root(str(ctx.root), "reuse-initiative")
        init_root.mkdir(parents=True)
        (init_root / "README.md").write_text("# Already exists\n")

        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.initiative_created is False
        assert "Already exists" in (init_root / "README.md").read_text()

    def test_promotion_result_includes_all_expected_fields(self, promo_repo) -> None:
        store = promo_repo.store
        ctx = promo_repo

        ctx.write_strategy(
            ticket_in_horizon="Now",
            ticket_id="01JNX0000077",
            ticket_title="Complete Test",
        )
        ticket_id = ctx.create_ticket("Complete Test", "01JNX0000077")

        result = promote_ticket(ticket_id, store=store, cwd=ctx.root)

        assert result.ticket_id == ticket_id
        assert result.initiative_slug == "complete-test"
        assert result.epic is not None
        assert result.link is not None
        assert result.strategy_updated is True
        assert isinstance(result.strategy_diagnostics, list)
        assert result.initiative_created is True
        assert result.epic_created is True
