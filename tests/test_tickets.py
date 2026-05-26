"""Tests for megaplan/tickets/ — local-only (FileStore) and cloud (DBStore) modes.

Covers:
  (1) Local-only: new, stdin body, list, show, edit, link/unlink, status transitions,
      address_resolved_by_epic walks files idempotently.
  (2) Cloud: same ops do file + DB write-through; link --resolves writes both.
  (3) Codebase auto-registration: first ticket new in fresh repo creates codebases
      row with root_commit_sha NON-NULL.
  (4) DBStore hook with associated codebase.
  (5) DBStore hook no associated codebase: SQL UPDATE flips DB row; file walk skipped.
  (6) FileStore hook: record_epic_event walks self.root/.megaplan/tickets/ and flips
      frontmatter.
  (7) Hook gating: wrong state / wrong event_type → no fire.
  (8) Multi-repo: two codebases at distinct repo_workspace; transition for codebase A
      only touches A's .megaplan/tickets/.
  (9) Identity: rename repo (same root_commit_sha → same codebase_id); no-commits repo
      errors cleanly.
"""

from __future__ import annotations

import os
import subprocess
import sys
import hashlib
from pathlib import Path
from unittest import mock

import pytest
import yaml

from megaplan.store import MultiStore, StoreError
from megaplan.store.file import FileStore
from megaplan.tickets import (
    address_resolved_by_epic,
    addressed,
    create_ticket,
    dismiss,
    edit,
    is_cloud_store,
    link,
    list_tickets,
    new,
    reopen,
    show,
    unlink,
)
from megaplan.tickets.files import (
    iterate_ticket_files,
    read_ticket_file,
    slugify,
    ticket_file_path,
    tickets_dir,
    write_ticket_file,
)
from megaplan.tickets.identity import repo_codebase_identity, repo_root_sha


# ---------------------------------------------------------------------------
# helpers — git repos in tmp_path
# ---------------------------------------------------------------------------


def _init_git_repo(repo_root: Path, *, with_commit: bool = True) -> str:
    """Create a git repo in *repo_root*, make an initial commit, and return the root SHA."""
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Megaplan Tests"],
        cwd=repo_root, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=repo_root, check=True, capture_output=True, text=True,
    )
    if with_commit:
        (repo_root / "README.md").write_text("# Test\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True, text=True,
        )
        result = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip().split("\n")[0]
    return ""


def _git_init_no_commits(repo_root: Path) -> None:
    """Init a git repo but make NO commits (so rev-list --max-parents=0 fails)."""
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Megaplan Tests"],
        cwd=repo_root, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=repo_root, check=True, capture_output=True, text=True,
    )


def _add_remote(repo_root: Path, remote_url: str) -> None:
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=repo_root, check=True, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# (1) Local-only mode tests
# ---------------------------------------------------------------------------


class TestLocalOnlyNew:
    """ticket new in local-only mode (no DBStore)."""

    def test_new_creates_file_and_returns_ulid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create a ticket in a git repo; assert the .md file is written and ULID returned."""
        _init_git_repo(tmp_path)
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")  # human source
        # Clear any MEGAPLAN_BACKEND so we stay local-only
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        captured: list[str] = []

        def _capture_print(*args, **kwargs):
            captured.append(" ".join(str(a) for a in args))

        import builtins
        monkeypatch.setattr(builtins, "print", _capture_print)

        ticket_id = new("Test ticket", body="A body", tags=["bug"], cwd=tmp_path)

        assert ticket_id
        assert len(captured) == 1
        assert captured[0] == ticket_id

        # File should exist
        slug = slugify("Test ticket")
        fpath = ticket_file_path(tmp_path, ticket_id, slug)
        assert fpath.exists()

        fm = read_ticket_file(fpath)
        assert fm is not None
        assert fm["title"] == "Test ticket"
        assert fm["status"] == "open"
        assert fm["source"] == "human"
        assert fm["tags"] == ["bug"]
        assert fm["__body__"] == "A body"

    def test_new_stdin_body(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create a ticket with body='-'; reads from stdin."""
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        monkeypatch.setattr(sys, "stdin", mock.MagicMock())
        sys.stdin.read.return_value = "Body from stdin\n"  # type: ignore[union-attr]

        ticket_id = new("stdin ticket", body="-", cwd=tmp_path)
        slug = slugify("stdin ticket")
        fpath = ticket_file_path(tmp_path, ticket_id, slug)
        fm = read_ticket_file(fpath)
        assert fm is not None
        assert fm["__body__"] == "Body from stdin"

    def test_new_stdin_empty_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reject empty stdin body."""
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        monkeypatch.setattr(sys, "stdin", mock.MagicMock())
        sys.stdin.read.return_value = "   \n"  # type: ignore[union-attr]

        with pytest.raises(ValueError, match="stdin body is empty"):
            new("stdin empty", body="-", cwd=tmp_path)

    def test_new_agent_source_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When MEGAPLAN_TURN_ID is set, source='agent' and filed_in_turn_id is populated."""
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "plan_worker_t1")
        monkeypatch.setenv("MEGAPLAN_ACTOR_ID", "actor-1")

        ticket_id = new("agent ticket", body="body", cwd=tmp_path)
        slug = slugify("agent ticket")
        fpath = ticket_file_path(tmp_path, ticket_id, slug)
        fm = read_ticket_file(fpath)
        assert fm is not None
        assert fm["source"] == "agent"
        assert fm["filed_in_turn_id"] == "plan_worker_t1"
        assert fm["filed_by_actor_id"] == "actor-1"


class TestStoreBackedFacade:
    """Facade operations routed through the Store protocol."""

    def test_file_store_facade_round_trip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        sha = _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        store = FileStore(tmp_path / "store", repo_root=tmp_path)

        ticket_id = new("Store ticket", body="store body", tags=["bug"], store=store, cwd=tmp_path)
        codebase = store.resolve_codebase_by_root_sha(sha)
        assert codebase is not None

        listed = list_tickets(status="open", tags=["bug"], store=store, cwd=tmp_path)
        assert [item["id"] for item in listed] == [ticket_id]

        shown = show(ticket_id, store=store, cwd=tmp_path)
        assert shown is not None
        assert shown["codebase_id"] == codebase.id
        assert shown["body"] == "store body"

        edit(ticket_id, title="Store ticket edited", add_tag="p0", store=store, cwd=tmp_path)
        link(ticket_id, "EPIC-1", resolves=True, store=store, cwd=tmp_path)
        assert store.list_ticket_epic_links(ticket_id=ticket_id)[0].epic_id == "EPIC-1"

        updated = address_resolved_by_epic("EPIC-1", store=store, repo_root=tmp_path)
        assert updated == [ticket_id]
        assert store.load_ticket(ticket_id).status == "addressed"

        unlink(ticket_id, "EPIC-1", store=store, cwd=tmp_path)
        assert store.list_ticket_epic_links(ticket_id=ticket_id) == []

    def test_file_store_facade_no_origin_identity_uses_local_metadata(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sha = _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        store = FileStore(tmp_path / "store", repo_root=tmp_path)

        ticket_id = new("No origin store ticket", body="body", store=store, cwd=tmp_path)

        ticket = store.load_ticket(ticket_id)
        assert ticket is not None
        codebase = store.load_codebase(ticket.codebase_id)
        assert codebase is not None
        expected_path_hash = hashlib.sha256(str(tmp_path.resolve()).encode("utf-8")).hexdigest()[:12]
        assert codebase.owner == "local"
        assert codebase.name == f"{slugify(tmp_path.name)}-{expected_path_hash}-{sha[:12]}"
        assert codebase.default_branch == "main"
        assert codebase.root_commit_sha == sha

    def test_file_store_facade_refuses_repo_without_root_sha_before_writing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _git_init_no_commits(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        store = FileStore(tmp_path / "store", repo_root=tmp_path)

        with pytest.raises(subprocess.CalledProcessError):
            new("No root facade ticket", body="body", store=store, cwd=tmp_path)

        assert list(iterate_ticket_files(tmp_path)) == []
        assert store.list_tickets() == []

    def test_multi_store_facade_round_trip_routes_through_store_predicate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        file_repo = tmp_path / "file-repo"
        db_repo = tmp_path / "db-repo"
        sha = _init_git_repo(file_repo)
        _init_git_repo(db_repo)
        file_store = FileStore(tmp_path / "file-store", repo_root=file_repo)
        db_store = FileStore(tmp_path / "db-store", repo_root=db_repo)
        store = MultiStore(file_store=file_store, db_store=db_store)
        epic = store.create_epic(title="Multi facade epic", goal="g", body="body", home_backend="file")

        ticket_id = new("Multi facade ticket", body="body", tags=["multi"], store=store, cwd=file_repo)

        codebase = store.resolve_codebase_by_root_sha(sha)
        assert codebase is not None
        assert file_store.load_ticket(ticket_id) is not None
        assert db_store.load_ticket(ticket_id) is not None
        assert [item["id"] for item in list_tickets(status="open", store=store, cwd=file_repo)] == [ticket_id]
        assert show(ticket_id, store=store, cwd=file_repo)["codebase_id"] == codebase.id
        with pytest.raises(StoreError, match="exists in both file and db backends"):
            link(ticket_id, epic.id, resolves=True, store=store, cwd=file_repo)


class TestLocalOnlyListShow:
    """list and show in local-only mode."""

    def test_list_returns_all(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        t1 = new("Ticket 1", body="b1", cwd=tmp_path)
        t2 = new("Ticket 2", body="b2", tags=["feature"], cwd=tmp_path)

        results = list_tickets(cwd=tmp_path)
        ids = {r["id"] for r in results}
        assert t1 in ids
        assert t2 in ids

    def test_list_filter_status(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        new("Open one", body="b", cwd=tmp_path)
        tid = new("Will be dismissed", body="b", cwd=tmp_path)
        dismiss(tid, reason="not needed", cwd=tmp_path)

        open_results = list_tickets(status="open", cwd=tmp_path)
        assert len(open_results) == 1
        assert open_results[0]["status"] == "open"

        dismissed_results = list_tickets(status="dismissed", cwd=tmp_path)
        assert len(dismissed_results) == 1
        assert dismissed_results[0]["status"] == "dismissed"

    def test_list_filter_tags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        new("Bug ticket", body="b", tags=["bug", "p0"], cwd=tmp_path)
        new("Feature ticket", body="b", tags=["feature"], cwd=tmp_path)

        bug_results = list_tickets(tags=["bug"], cwd=tmp_path)
        assert len(bug_results) == 1
        assert "bug" in bug_results[0]["tags"]

    def test_show_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("Show me", body="details", cwd=tmp_path)

        result = show(tid, cwd=tmp_path)
        assert result is not None
        assert result["id"] == tid
        assert result["title"] == "Show me"
        assert result["body"] == "details"

    def test_show_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        result = show("nonexistent", cwd=tmp_path)
        assert result is None


class TestLocalOnlyEdit:
    """Edit tickets in local-only mode."""

    def test_edit_title(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("Old title", body="b", cwd=tmp_path)

        result = edit(tid, title="New title", cwd=tmp_path)
        assert result is not None
        assert result["title"] == "New title"

        # Verify on disk
        fm = show(tid, cwd=tmp_path)
        assert fm["title"] == "New title"

    def test_edit_body(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("T", body="old", cwd=tmp_path)

        edit(tid, body="new body", cwd=tmp_path)
        fm = show(tid, cwd=tmp_path)
        assert fm["body"] == "new body"

    def test_edit_add_remove_tags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("T", body="b", tags=["a", "b"], cwd=tmp_path)

        edit(tid, add_tag="c", cwd=tmp_path)
        fm = show(tid, cwd=tmp_path)
        assert set(fm["tags"]) == {"a", "b", "c"}

        edit(tid, remove_tag="a", cwd=tmp_path)
        fm = show(tid, cwd=tmp_path)
        assert set(fm["tags"]) == {"b", "c"}

    def test_edit_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        result = edit("nonexistent", title="Nope", cwd=tmp_path)
        assert result is None


class TestLocalOnlyLinkUnlink:
    """link / unlink in local-only mode."""

    def test_link_updates_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("Linked ticket", body="b", cwd=tmp_path)

        result = link(tid, "E1", resolves=True, cwd=tmp_path)
        assert result is not None
        epics = result.get("epics", [])
        assert len(epics) == 1
        assert epics[0]["epic_id"] == "E1"
        assert epics[0]["resolves_on_complete"] is True

        # Re-read from file
        fm = show(tid, cwd=tmp_path)
        assert len(fm["epics"]) == 1

    def test_unlink_removes_from_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("T", body="b", cwd=tmp_path)
        link(tid, "E1", cwd=tmp_path)
        link(tid, "E2", cwd=tmp_path)

        unlink(tid, "E1", cwd=tmp_path)
        fm = show(tid, cwd=tmp_path)
        epics = fm["epics"]
        assert len(epics) == 1
        assert epics[0]["epic_id"] == "E2"

    def test_link_idempotent_re_link(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Re-linking the same epic updates the resolves flag."""
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("T", body="b", cwd=tmp_path)
        link(tid, "E1", resolves=False, cwd=tmp_path)
        link(tid, "E1", resolves=True, cwd=tmp_path)

        fm = show(tid, cwd=tmp_path)
        epics = [e for e in fm["epics"] if e["epic_id"] == "E1"]
        assert len(epics) == 1
        assert epics[0]["resolves_on_complete"] is True

    def test_link_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        result = link("nonexistent", "E1", cwd=tmp_path)
        assert result is None


class TestLocalOnlyStatusTransitions:
    """addressed / dismiss / reopen in local-only mode."""

    def test_addressed_sets_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("T", body="b", cwd=tmp_path)

        result = addressed(tid, note="Fixed by PR #5", cwd=tmp_path)
        assert result is not None
        assert result["status"] == "addressed"
        assert result["resolution_note"] == "Fixed by PR #5"
        assert result["addressed_at"] is not None

    def test_dismiss_sets_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("T", body="b", cwd=tmp_path)

        result = dismiss(tid, reason="Won't fix", cwd=tmp_path)
        assert result is not None
        assert result["status"] == "dismissed"
        assert result["resolution_note"] == "Won't fix"

    def test_reopen_clears_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_git_repo(tmp_path)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)
        tid = new("T", body="b", cwd=tmp_path)
        addressed(tid, note="done", cwd=tmp_path)

        result = reopen(tid, cwd=tmp_path)
        assert result is not None
        assert result["status"] == "open"
        assert result["resolution_note"] is None
        assert result["addressed_at"] is None


# ---------------------------------------------------------------------------
# (6) FileStore hook — address_resolved_by_epic via FileStore
# ---------------------------------------------------------------------------


class TestFileStoreHook:
    """FileStore.record_epic_event triggers address_resolved_by_epic."""

    def test_hook_flips_file_frontmatter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create a ticket linked with resolves_on_complete=true in a repo under FileStore root,
        fire record_epic_event with state='done', assert file flips."""
        repo_root = tmp_path / "repo"
        _init_git_repo(repo_root)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        tid = new("Ticket to address", body="b", cwd=repo_root)
        link(tid, "E1", resolves=True, cwd=repo_root)

        # Create a FileStore that uses repo_root (which has .megaplan/tickets/)
        fs = FileStore(repo_root)

        from megaplan.store.base import EpicEvent
        from datetime import datetime, timezone

        fs.record_epic_event(
            epic_id="E1",
            transaction_id="tx-1",
            event_type="state_change",
            summary="Epic done",
            prior_state={"state": "in_progress"},
            pre_state={"state": "in_progress"},
            post_state={"state": "done"},
        )

        # Verify the file flipped
        fm = show(tid, cwd=repo_root)
        assert fm is not None
        assert fm["status"] == "addressed"
        assert "Resolved by epic E1" in (fm.get("resolution_note") or "")

    def test_hook_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Second call to record_epic_event is no-op (status already addressed)."""
        repo_root = tmp_path / "repo"
        _init_git_repo(repo_root)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        tid = new("Ticket", body="b", cwd=repo_root)
        link(tid, "E1", resolves=True, cwd=repo_root)

        fs = FileStore(repo_root)
        fs.record_epic_event(
            epic_id="E1",
            transaction_id="tx-1",
            event_type="state_change",
            summary="done",
            prior_state={"state": "in_progress"},
            pre_state={"state": "in_progress"},
            post_state={"state": "done"},
        )

        # Second call — should be no-op (idempotent)
        updated = address_resolved_by_epic("E1", store=fs, repo_root=repo_root)
        assert updated == []  # no tickets changed

    def test_hook_skips_when_no_tickets_dir(self, tmp_path: Path) -> None:
        """When tickets_dir does not exist, file walk skips cleanly."""
        repo_root = tmp_path / "repo"
        _init_git_repo(repo_root)

        fs = FileStore(repo_root)
        # No tickets directory yet — should not error
        updated = address_resolved_by_epic("E1", store=fs, repo_root=repo_root)
        assert updated == []

    def test_hook_skips_when_repo_root_none(self, tmp_path: Path) -> None:
        """When repo_root is None, file walk is skipped cleanly."""
        fs = FileStore(tmp_path)

        updated = address_resolved_by_epic("E1", store=fs, repo_root=None)
        assert updated == []


# ---------------------------------------------------------------------------
# (7) Hook gating
# ---------------------------------------------------------------------------


class TestHookGating:
    """record_epic_event only fires address_resolved_by_epic on correct gate."""

    def test_wrong_state_no_fire(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """event_type='state_change' but post_state.state='in_progress' → no fire."""
        repo_root = tmp_path / "repo"
        _init_git_repo(repo_root)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        tid = new("T", body="b", cwd=repo_root)
        link(tid, "E1", resolves=True, cwd=repo_root)

        fs = FileStore(repo_root)
        fs.record_epic_event(
            epic_id="E1",
            transaction_id="tx-1",
            event_type="state_change",
            summary="progress",
            prior_state={"state": "planned"},
            pre_state={"state": "planned"},
            post_state={"state": "in_progress"},
        )

        fm = show(tid, cwd=repo_root)
        assert fm["status"] == "open"  # unchanged

    def test_wrong_event_type_no_fire(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """post_state.state='done' but event_type is not 'state_change' → no fire."""
        repo_root = tmp_path / "repo"
        _init_git_repo(repo_root)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        tid = new("T", body="b", cwd=repo_root)
        link(tid, "E1", resolves=True, cwd=repo_root)

        fs = FileStore(repo_root)
        fs.record_epic_event(
            epic_id="E1",
            transaction_id="tx-1",
            event_type="body_edit",  # not state_change
            summary="note",
            prior_state={"state": "in_progress"},
            pre_state={"state": "in_progress"},
            post_state={"state": "done"},
        )

        fm = show(tid, cwd=repo_root)
        assert fm["status"] == "open"  # unchanged


# ---------------------------------------------------------------------------
# (8) Multi-repo — file-level isolation
# ---------------------------------------------------------------------------


class TestMultiRepoIsolation:
    """Two repos with distinct tickets; transition for one only touches its tickets."""

    def test_file_walk_only_touches_target_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_a = tmp_path / "repoA"
        repo_b = tmp_path / "repoB"
        _init_git_repo(repo_a)
        _init_git_repo(repo_b)
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        ta = new("Ticket A", body="b", cwd=repo_a)
        link(ta, "E1", resolves=True, cwd=repo_a)

        tb = new("Ticket B", body="b", cwd=repo_b)
        link(tb, "E1", resolves=True, cwd=repo_b)

        # Fire hook for repo A only
        address_resolved_by_epic("E1", repo_root=repo_a)

        # Repo A ticket should be addressed
        fm_a = show(ta, cwd=repo_a)
        assert fm_a["status"] == "addressed"

        # Repo B ticket should still be open
        fm_b = show(tb, cwd=repo_b)
        assert fm_b["status"] == "open"


# ---------------------------------------------------------------------------
# (9) Identity helpers
# ---------------------------------------------------------------------------


class TestIdentity:
    """Git identity resolution — repo_root_sha, rename, no-commits error."""

    def test_repo_root_sha_returns_sha(self, tmp_path: Path) -> None:
        sha = _init_git_repo(tmp_path)
        result = repo_root_sha(tmp_path)
        assert result == sha

    def test_rename_repo_same_root_sha(self, tmp_path: Path) -> None:
        """Renaming/moving a repo should preserve the same root_commit_sha."""
        sha = _init_git_repo(tmp_path)
        # Moving shouldn't change the root SHA
        new_path = tmp_path.parent / "renamed_repo"
        tmp_path.rename(new_path)
        result = repo_root_sha(new_path)
        assert result == sha

    def test_no_commits_repo_errors(self, tmp_path: Path) -> None:
        """A git repo with no commits errors cleanly."""
        _git_init_no_commits(tmp_path)
        with pytest.raises(subprocess.CalledProcessError):
            repo_root_sha(tmp_path)

    def test_repo_codebase_identity_requires_root_sha(self, tmp_path: Path) -> None:
        _git_init_no_commits(tmp_path)
        with pytest.raises(subprocess.CalledProcessError):
            repo_codebase_identity(tmp_path)

    def test_repo_codebase_identity_falls_back_without_origin(self, tmp_path: Path) -> None:
        sha = _init_git_repo(tmp_path)
        identity = repo_codebase_identity(tmp_path)
        expected_path_hash = hashlib.sha256(str(tmp_path.resolve()).encode("utf-8")).hexdigest()[:12]
        assert identity.owner == "local"
        assert identity.name == f"{slugify(tmp_path.name)}-{expected_path_hash}-{sha[:12]}"
        assert identity.default_branch == "main"
        assert identity.root_commit_sha == sha

    def test_slugify(self) -> None:
        assert slugify("Hello World!") == "hello-world"
        assert slugify("  Foo & Bar  ") == "foo-bar"
        assert slugify("") == ""


# ---------------------------------------------------------------------------
# (2)(3)(4)(5) DBStore-dependent tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("SUPABASE_DB_URL") is None,
    reason="SUPABASE_DB_URL not set; DBStore tests require a live database.",
)
class TestDBStoreTickets:
    """Cloud-mode ticket operations via DBStore fixture.

    These tests require ``--backend db`` and ``SUPABASE_DB_URL`` to be set.
    """

    def test_new_writes_file_and_db(
        self,
        db_store_factory,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ticket new in cloud mode writes .md file AND inserts a DB row."""
        _init_git_repo(tmp_path)
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            ticket_id = new("Cloud ticket", body="body", tags=["cloud"], store=store, cwd=tmp_path)

            # File should exist
            slug = slugify("Cloud ticket")
            fpath = ticket_file_path(tmp_path, ticket_id, slug)
            assert fpath.exists()

            # DB row should exist
            db_ticket = store.load_ticket(ticket_id)
            assert db_ticket is not None
            assert db_ticket.title == "Cloud ticket"
            assert db_ticket.status == "open"
            if db_ticket.tags:
                assert "cloud" in db_ticket.tags
        finally:
            store.close()

    def test_codebase_auto_registration(
        self,
        db_store_factory,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """First ticket new in a fresh repo creates a codebases row with NON-NULL root_commit_sha."""
        sha = _init_git_repo(tmp_path)
        _add_remote(tmp_path, "https://github.com/test-owner/test-repo.git")
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            # Verify codebase doesn't exist yet
            existing = store.resolve_codebase_by_root_sha(sha)
            assert existing is None

            ticket_id = new("First ticket", body="body", store=store, cwd=tmp_path)

            # Now the codebase should exist
            cb = store.resolve_codebase_by_root_sha(sha)
            assert cb is not None
            assert cb.root_commit_sha == sha
            assert cb.owner == "test-owner"
            assert cb.name == "test-repo"

            # Second ticket should reuse the same codebase
            ticket_id2 = new("Second ticket", body="body", store=store, cwd=tmp_path)
            cb2 = store.resolve_codebase_by_root_sha(sha)
            assert cb2 is not None
            assert cb2.id == cb.id
        finally:
            store.close()

    def test_codebase_auto_registration_without_origin_uses_local_fallback(
        self,
        db_store_factory,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sha = _init_git_repo(tmp_path)
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            ticket_id = new("First ticket", body="body", store=store, cwd=tmp_path)
            assert ticket_id

            cb = store.resolve_codebase_by_root_sha(sha)
            assert cb is not None
            expected_path_hash = hashlib.sha256(str(tmp_path.resolve()).encode("utf-8")).hexdigest()[:12]
            assert cb.owner == "local"
            assert cb.name == f"{slugify(tmp_path.name)}-{expected_path_hash}-{sha[:12]}"
            assert cb.default_branch == "main"
            assert cb.root_commit_sha == sha
        finally:
            store.close()

    def test_link_resolves_writes_both(
        self,
        db_store_factory,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """link --resolves updates both file frontmatter AND DB join row."""
        _init_git_repo(tmp_path)
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            ticket_id = new("L ticket", body="body", store=store, cwd=tmp_path)

            result = link(ticket_id, "E99", resolves=True, store=store, cwd=tmp_path)
            assert result is not None

            # Check file
            fm = show(ticket_id, cwd=tmp_path)
            assert len(fm["epics"]) == 1
            assert fm["epics"][0]["epic_id"] == "E99"
            assert fm["epics"][0]["resolves_on_complete"] is True

            # Check DB join
            links = store.list_ticket_epic_links(ticket_id=ticket_id)
            assert len(links) == 1
            assert links[0].epic_id == "E99"
            assert links[0].resolves_on_complete is True
        finally:
            store.close()

    def test_list_from_db(self, db_store_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """list_tickets queries the DB in cloud mode."""
        _init_git_repo(tmp_path)
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            new("List me", body="b", store=store, cwd=tmp_path)
            results = list_tickets(store=store, cwd=tmp_path)
            assert len(results) >= 1
        finally:
            store.close()

    def test_hook_with_associated_codebase(
        self,
        db_store_factory,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DBStore hook: codebase with associated_epic_id=E1 and repo_workspace set.
        Ticket linked to E1 with resolves_on_complete=true. Fire record_epic_event.
        Assert file flips AND DB row flips; second call is no-op."""
        _init_git_repo(tmp_path)
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            sha = repo_root_sha(tmp_path)
            # Create a codebase with associated_epic_id and repo_workspace
            cb = store.create_codebase(
                owner="test-owner",
                name="test-repo",
                default_branch="main",
                repo_workspace=str(tmp_path),
                associated_epic_id="HOOK-E1",
                root_commit_sha=sha,
            )

            # Create ticket in this codebase
            ticket_id = store.create_ticket(
                codebase_id=cb.id,
                title="Hook ticket",
                body="body",
                source="human",
                slug=slugify("Hook ticket"),
                ticket_id="HOOK-TICKET-1",
            ).id

            # Link to epic with resolves_on_complete
            store.link_ticket_to_epic(
                ticket_id=ticket_id,
                epic_id="HOOK-E1",
                resolves_on_complete=True,
            )

            # Also create the file so file walk works
            fpath = ticket_file_path(tmp_path, ticket_id, slugify("Hook ticket"))
            write_ticket_file(fpath, {
                "id": ticket_id,
                "title": "Hook ticket",
                "status": "open",
                "source": "human",
                "tags": [],
                "codebase_id": cb.id,
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_edited_at": "2026-01-01T00:00:00+00:00",
                "epics": [{"epic_id": "HOOK-E1", "resolves_on_complete": True, "linked_at": "2026-01-01T00:00:00+00:00"}],
                "__body__": "body",
            })

            # Fire record_epic_event with state='done'
            store.record_epic_event(
                epic_id="HOOK-E1",
                transaction_id="tx-hook-1",
                event_type="state_change",
                summary="Epic completed",
                prior_state={"state": "in_progress"},
                pre_state={"state": "in_progress"},
                post_state={"state": "done"},
            )

            # DB row should be flipped
            db_ticket = store.load_ticket(ticket_id)
            assert db_ticket is not None
            assert db_ticket.status == "addressed"

            # File should be flipped
            fm = read_ticket_file(fpath)
            assert fm is not None
            assert fm["status"] == "addressed"

            # Second call is no-op
            updated = store.address_tickets_resolved_by_epic("HOOK-E1")
            assert updated == []  # idempotent
        finally:
            store.close()

    def test_hook_no_associated_codebase(
        self,
        db_store_factory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DBStore hook with no associated codebase: SQL UPDATE flips DB row;
        file walk is skipped because repo_workspace is unavailable."""
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            # Create a codebase WITHOUT associated_epic_id
            cb = store.create_codebase(
                owner="no-assoc",
                name="no-assoc",
                default_branch="main",
                root_commit_sha="no-assoc-sha",
            )

            ticket_id = store.create_ticket(
                codebase_id=cb.id,
                title="No-assoc ticket",
                body="body",
                source="human",
                slug=slugify("No-assoc ticket"),
                ticket_id="NO-ASSOC-TICKET-1",
            ).id

            store.link_ticket_to_epic(
                ticket_id=ticket_id,
                epic_id="NO-ASSOC-E1",
                resolves_on_complete=True,
            )

            # Fire record_epic_event — load_codebase_by_associated_epic returns None
            # repo_root becomes None, file walk is skipped cleanly
            store.record_epic_event(
                epic_id="NO-ASSOC-E1",
                transaction_id="tx-no-assoc-1",
                event_type="state_change",
                summary="Epic done",
                prior_state={"state": "in_progress"},
                pre_state={"state": "in_progress"},
                post_state={"state": "done"},
            )

            # DB row should still be flipped (via SQL)
            db_ticket = store.load_ticket(ticket_id)
            assert db_ticket is not None
            assert db_ticket.status == "addressed"
        finally:
            store.close()

    def test_multi_repo_isolation(
        self,
        db_store_factory,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Two codebases at distinct repo_workspace; transition for codebase A
        only touches A's .megaplan/tickets/."""
        repo_a = tmp_path / "repoA"
        repo_b = tmp_path / "repoB"
        _init_git_repo(repo_a)
        _init_git_repo(repo_b)
        monkeypatch.setenv("MEGAPLAN_BACKEND", "db")
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "")

        store = db_store_factory()
        try:
            # Create two codebases
            cb_a = store.create_codebase(
                owner="a-owner", name="a-repo", default_branch="main",
                repo_workspace=str(repo_a), associated_epic_id="MULTI-E1",
                root_commit_sha=repo_root_sha(repo_a),
            )
            cb_b = store.create_codebase(
                owner="b-owner", name="b-repo", default_branch="main",
                repo_workspace=str(repo_b),
                root_commit_sha=repo_root_sha(repo_b),
            )

            # Tickets in both codebases, both linked to MULTI-E1
            ta = store.create_ticket(
                codebase_id=cb_a.id, title="A ticket", body="b", source="human",
                slug=slugify("A ticket"), ticket_id="MULTI-TA",
            ).id
            tb = store.create_ticket(
                codebase_id=cb_b.id, title="B ticket", body="b", source="human",
                slug=slugify("B ticket"), ticket_id="MULTI-TB",
            ).id

            store.link_ticket_to_epic(ticket_id=ta, epic_id="MULTI-E1", resolves_on_complete=True)
            store.link_ticket_to_epic(ticket_id=tb, epic_id="MULTI-E1", resolves_on_complete=True)

            # Also write files in both repos
            for repo, tid, title in [(repo_a, ta, "A ticket"), (repo_b, tb, "B ticket")]:
                fpath = ticket_file_path(repo, tid, slugify(title))
                write_ticket_file(fpath, {
                    "id": tid, "title": title, "status": "open", "source": "human",
                    "tags": [], "codebase_id": cb_a.id if repo == repo_a else cb_b.id,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "last_edited_at": "2026-01-01T00:00:00+00:00",
                    "epics": [{"epic_id": "MULTI-E1", "resolves_on_complete": True,
                               "linked_at": "2026-01-01T00:00:00+00:00"}],
                    "__body__": "b",
                })

            # Fire hook — only codebase A has associated_epic_id=MULTI-E1
            store.record_epic_event(
                epic_id="MULTI-E1",
                transaction_id="tx-multi-1",
                event_type="state_change",
                summary="Multi-repo epic done",
                prior_state={"state": "in_progress"},
                pre_state={"state": "in_progress"},
                post_state={"state": "done"},
            )

            # Only repo A's file should be flipped
            fm_a = read_ticket_file(ticket_file_path(repo_a, ta, slugify("A ticket")))
            assert fm_a is not None
            assert fm_a["status"] == "addressed"

            # Repo B's file should remain open
            fm_b = read_ticket_file(ticket_file_path(repo_b, tb, slugify("B ticket")))
            assert fm_b is not None
            assert fm_b["status"] == "open"

            # But both DB rows should be flipped (SQL doesn't filter by codebase)
            db_ta = store.load_ticket(ta)
            assert db_ta.status == "addressed"
            db_tb = store.load_ticket(tb)
            assert db_tb.status == "addressed"  # SQL flips all matching tickets
        finally:
            store.close()


# ---------------------------------------------------------------------------
# is_cloud_store predicate
# ---------------------------------------------------------------------------


class TestIsCloudStore:
    def test_file_store_is_cloud(self) -> None:
        fs = FileStore(Path("/tmp"))
        assert is_cloud_store(fs) is True

    def test_multi_store_is_cloud(self) -> None:
        fs = FileStore(Path("/tmp/file"))
        db = FileStore(Path("/tmp/db"))
        store = MultiStore(file_store=fs, db_store=db)
        assert is_cloud_store(store) is True

    def test_db_store_is_cloud(self, db_store_factory) -> None:
        store = db_store_factory()
        try:
            assert is_cloud_store(store) is True
        finally:
            store.close()
