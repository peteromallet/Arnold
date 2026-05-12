"""CLI-level tests for ``megaplan ticket ...`` subcommands.

Covers:
  (10) CLI happy paths via subprocess: ticket new stdout is exactly ULID+newline;
       list --json valid JSON; link --resolves round-trip.
  (11) Agent env: _codex_child_env returns env with MEGAPLAN_TURN_ID;
       spawn worker and assert filed ticket records source='agent'.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from megaplan.tickets.files import read_ticket_file, slugify, ticket_file_path
from megaplan.workers import _codex_child_env, _external_worker_env


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _init_git_repo(repo_root: Path) -> None:
    """Create a git repo with one commit."""
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo_root, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo_root, check=True, capture_output=True, text=True,
    )
    (repo_root / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_root, check=True, capture_output=True, text=True)


def _run_megaplan(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run megaplan as a subprocess and return the result."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    # Ensure local-only by unsetting MEGAPLAN_BACKEND
    merged_env.pop("MEGAPLAN_BACKEND", None)
    return subprocess.run(
        [sys.executable, "-m", "megaplan", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=merged_env,
    )


# ---------------------------------------------------------------------------
# (10) CLI happy paths via subprocess (local-only)
# ---------------------------------------------------------------------------


class TestCLIHappyPaths:
    """End-to-end CLI tests via subprocess."""

    def test_ticket_new_stdout_is_ulid_newline(self, tmp_path: Path) -> None:
        """``megaplan ticket new`` prints exactly ULID + newline to stdout on success."""
        _init_git_repo(tmp_path)

        proc = _run_megaplan(
            ["ticket", "new", "Test ticket", "-b", "A body"],
            cwd=tmp_path,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"

        # stdout should be exactly ULID + newline (ULIDs are 26 chars of Crockford base32)
        stdout = proc.stdout
        assert stdout.endswith("\n")
        ulid = stdout.strip()
        assert len(ulid) == 26  # ULID length
        # Should be alphanumeric uppercase
        assert all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in ulid)

    def test_ticket_new_creates_file(self, tmp_path: Path) -> None:
        """``megaplan ticket new`` creates a .md file in .megaplan/tickets/."""
        _init_git_repo(tmp_path)

        proc = _run_megaplan(
            ["ticket", "new", "File ticket", "-b", "File body", "--tags", "bug,urgent"],
            cwd=tmp_path,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        ulid = proc.stdout.strip()

        slug = slugify("File ticket")
        fpath = ticket_file_path(tmp_path, ulid, slug)
        assert fpath.exists()
        fm = read_ticket_file(fpath)
        assert fm is not None
        assert fm["title"] == "File ticket"
        assert fm["__body__"] == "File body"
        assert set(fm.get("tags", [])) == {"bug", "urgent"}

    def test_ticket_list_json(self, tmp_path: Path) -> None:
        """``megaplan ticket list --json`` outputs valid JSON."""
        _init_git_repo(tmp_path)

        _run_megaplan(["ticket", "new", "T1", "-b", "b1"], cwd=tmp_path)
        _run_megaplan(["ticket", "new", "T2", "-b", "b2"], cwd=tmp_path)

        proc = _run_megaplan(["ticket", "list", "--json"], cwd=tmp_path)
        assert proc.returncode == 0, f"stderr: {proc.stderr}"

        data = json.loads(proc.stdout)
        assert isinstance(data, list)
        assert len(data) >= 2
        titles = {t["title"] for t in data}
        assert "T1" in titles
        assert "T2" in titles

    def test_ticket_list_filter_status(self, tmp_path: Path) -> None:
        """``megaplan ticket list --status dismissed`` filters correctly."""
        _init_git_repo(tmp_path)

        _run_megaplan(["ticket", "new", "Open", "-b", "b"], cwd=tmp_path)
        proc2 = _run_megaplan(["ticket", "new", "Dismissed", "-b", "b"], cwd=tmp_path)
        dismissed_ulid = proc2.stdout.strip()

        _run_megaplan(["ticket", "dismiss", dismissed_ulid, "--reason", "nope"], cwd=tmp_path)

        proc = _run_megaplan(["ticket", "list", "--status", "dismissed", "--json"], cwd=tmp_path)
        data = json.loads(proc.stdout)
        assert len(data) == 1
        assert data[0]["title"] == "Dismissed"

    def test_ticket_show_json(self, tmp_path: Path) -> None:
        """``megaplan ticket show <id> --json`` outputs valid JSON."""
        _init_git_repo(tmp_path)

        proc_new = _run_megaplan(["ticket", "new", "Show me", "-b", "details"], cwd=tmp_path)
        ulid = proc_new.stdout.strip()

        proc = _run_megaplan(["ticket", "show", ulid, "--json"], cwd=tmp_path)
        data = json.loads(proc.stdout)
        assert data["id"] == ulid
        assert data["title"] == "Show me"
        assert data["body"] == "details"

    def test_ticket_link_resolves_round_trip(self, tmp_path: Path) -> None:
        """``megaplan ticket link <ticket> <epic> --resolves`` round-trips through show."""
        _init_git_repo(tmp_path)

        proc_new = _run_megaplan(["ticket", "new", "Link me", "-b", "body"], cwd=tmp_path)
        ulid = proc_new.stdout.strip()

        proc_link = _run_megaplan(
            ["ticket", "link", ulid, "EPIC42", "--resolves"],
            cwd=tmp_path,
        )
        assert proc_link.returncode == 0, f"stderr: {proc_link.stderr}"

        # Verify via show
        proc_show = _run_megaplan(["ticket", "show", ulid, "--json"], cwd=tmp_path)
        data = json.loads(proc_show.stdout)
        epics = data.get("epics", [])
        assert len(epics) == 1
        assert epics[0]["epic_id"] == "EPIC42"
        assert epics[0]["resolves_on_complete"] is True

    def test_ticket_unlink_round_trip(self, tmp_path: Path) -> None:
        """``megaplan ticket unlink`` removes the epic from the ticket."""
        _init_git_repo(tmp_path)

        proc_new = _run_megaplan(["ticket", "new", "Unlink me", "-b", "body"], cwd=tmp_path)
        ulid = proc_new.stdout.strip()

        _run_megaplan(["ticket", "link", ulid, "E1"], cwd=tmp_path)
        _run_megaplan(["ticket", "link", ulid, "E2"], cwd=tmp_path)

        proc_unlink = _run_megaplan(["ticket", "unlink", ulid, "E1"], cwd=tmp_path)
        assert proc_unlink.returncode == 0

        proc_show = _run_megaplan(["ticket", "show", ulid, "--json"], cwd=tmp_path)
        data = json.loads(proc_show.stdout)
        epics = data.get("epics", [])
        assert len(epics) == 1
        assert epics[0]["epic_id"] == "E2"

    def test_ticket_edit_status(self, tmp_path: Path) -> None:
        """Edit a ticket's fields via CLI."""
        _init_git_repo(tmp_path)

        proc_new = _run_megaplan(["ticket", "new", "Edit me", "-b", "old"], cwd=tmp_path)
        ulid = proc_new.stdout.strip()

        _run_megaplan(
            ["ticket", "edit", ulid, "--title", "Edited", "--body", "new", "--status", "dismissed"],
            cwd=tmp_path,
        )

        proc_show = _run_megaplan(["ticket", "show", ulid, "--json"], cwd=tmp_path)
        data = json.loads(proc_show.stdout)
        assert data["title"] == "Edited"
        assert data["body"] == "new"
        assert data["status"] == "dismissed"

    def test_ticket_addressed_dismiss_reopen(self, tmp_path: Path) -> None:
        """Full status transition cycle via CLI."""
        _init_git_repo(tmp_path)

        proc_new = _run_megaplan(["ticket", "new", "Cycle", "-b", "body"], cwd=tmp_path)
        ulid = proc_new.stdout.strip()

        # addressed
        _run_megaplan(["ticket", "addressed", ulid, "--note", "done"], cwd=tmp_path)
        data = json.loads(
            _run_megaplan(["ticket", "show", ulid, "--json"], cwd=tmp_path).stdout
        )
        assert data["status"] == "addressed"

        # reopen
        _run_megaplan(["ticket", "reopen", ulid], cwd=tmp_path)
        data = json.loads(
            _run_megaplan(["ticket", "show", ulid, "--json"], cwd=tmp_path).stdout
        )
        assert data["status"] == "open"

        # dismiss
        _run_megaplan(["ticket", "dismiss", ulid, "--reason", "wontfix"], cwd=tmp_path)
        data = json.loads(
            _run_megaplan(["ticket", "show", ulid, "--json"], cwd=tmp_path).stdout
        )
        assert data["status"] == "dismissed"

    def test_ticket_not_found_errors(self, tmp_path: Path) -> None:
        """CLI errors gracefully when a ticket is not found."""
        _init_git_repo(tmp_path)

        proc = _run_megaplan(["ticket", "show", "nonexistent"], cwd=tmp_path)
        assert proc.returncode != 0

    def test_ticket_new_with_stdin(self, tmp_path: Path) -> None:
        """ticket new with '-' reads from stdin."""
        _init_git_repo(tmp_path)

        proc = subprocess.run(
            [sys.executable, "-m", "megaplan", "ticket", "new", "Stdin ticket", "-"],
            cwd=tmp_path,
            input="Body from stdin\n",
            capture_output=True,
            text=True,
            env={**os.environ, "MEGAPLAN_BACKEND": ""},
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        ulid = proc.stdout.strip()
        assert len(ulid) == 26

        slug = slugify("Stdin ticket")
        fpath = ticket_file_path(tmp_path, ulid, slug)
        fm = read_ticket_file(fpath)
        assert fm is not None
        assert fm["__body__"] == "Body from stdin"


# ---------------------------------------------------------------------------
# (11) Agent env — _codex_child_env / _external_worker_env synthetic markers
# ---------------------------------------------------------------------------


class TestAgentEnv:
    """MEGAPLAN_TURN_ID injection via _codex_child_env and _external_worker_env."""

    def test_codex_child_env_injects_turn_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_codex_child_env(turn_id='plan_worker_p1') returns env with MEGAPLAN_TURN_ID."""
        monkeypatch.delenv("MEGAPLAN_TURN_ID", raising=False)
        monkeypatch.delenv("MEGAPLAN_ACTOR_ID", raising=False)

        env = _codex_child_env(turn_id="plan_worker_p1")
        assert env["MEGAPLAN_TURN_ID"] == "plan_worker_p1"

    def test_codex_child_env_injects_actor_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_codex_child_env(actor_id='actor-1') returns env with MEGAPLAN_ACTOR_ID."""
        monkeypatch.delenv("MEGAPLAN_ACTOR_ID", raising=False)

        env = _codex_child_env(actor_id="actor-1")
        assert env["MEGAPLAN_ACTOR_ID"] == "actor-1"

    def test_external_worker_env_injects_turn_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_external_worker_env(turn_id='plan_worker_p2') returns env with MEGAPLAN_TURN_ID."""
        monkeypatch.delenv("MEGAPLAN_TURN_ID", raising=False)

        env = _external_worker_env(turn_id="plan_worker_p2")
        assert env["MEGAPLAN_TURN_ID"] == "plan_worker_p2"

    def test_no_turn_id_means_no_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When turn_id=None, MEGAPLAN_TURN_ID is NOT injected."""
        monkeypatch.delenv("MEGAPLAN_TURN_ID", raising=False)

        env = _codex_child_env()  # no turn_id
        assert "MEGAPLAN_TURN_ID" not in env

    def test_worker_filed_ticket_records_agent_source(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Simulate a worker invocation: set MEGAPLAN_TURN_ID in env, create ticket,
        assert source='agent' and filed_in_turn_id set."""
        _init_git_repo(tmp_path)
        monkeypatch.setenv("MEGAPLAN_TURN_ID", "plan_worker_p1")
        monkeypatch.delenv("MEGAPLAN_BACKEND", raising=False)

        from megaplan.tickets import new

        ticket_id = new("Agent-filed ticket", body="Found a bug", cwd=tmp_path)
        slug = slugify("Agent-filed ticket")
        fpath = ticket_file_path(tmp_path, ticket_id, slug)
        fm = read_ticket_file(fpath)

        assert fm is not None
        assert fm["source"] == "agent"
        assert fm["filed_in_turn_id"] == "plan_worker_p1"

    def test_cli_with_turn_id_env(self, tmp_path: Path) -> None:
        """Run megaplan ticket new via subprocess with MEGAPLAN_TURN_ID set,
        verify the resulting file records source='agent'."""
        _init_git_repo(tmp_path)

        proc = subprocess.run(
            [sys.executable, "-m", "megaplan", "ticket", "new", "Agent CLI ticket", "-b", "cli body"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "MEGAPLAN_BACKEND": "",
                "MEGAPLAN_TURN_ID": "plan_worker_cli_test",
            },
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        ulid = proc.stdout.strip()

        slug = slugify("Agent CLI ticket")
        fpath = ticket_file_path(tmp_path, ulid, slug)
        fm = read_ticket_file(fpath)
        assert fm is not None
        assert fm["source"] == "agent"
        assert fm["filed_in_turn_id"] == "plan_worker_cli_test"


# ---------------------------------------------------------------------------
# CLI subparser registration check (extend test_cli_entry)
# ---------------------------------------------------------------------------


class TestTicketSubparserRegistration:
    """Verify the 'ticket' subcommand is registered with every expected verb."""

    def test_ticket_subparser_has_all_verbs(self) -> None:
        import argparse
        from megaplan.cli import build_parser

        parser = build_parser()
        ticket_parser = None
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                if "ticket" in action.choices:
                    ticket_parser = action.choices["ticket"]
                    break

        assert ticket_parser is not None, "ticket subparser not registered"

        for action in ticket_parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                verbs = set(action.choices.keys())
                expected = {
                    "new", "list", "show", "edit", "link", "unlink",
                    "addressed", "dismiss", "reopen", "search",
                }
                assert verbs == expected, f"Got verbs: {verbs}"
                return

        raise AssertionError("ticket subparser did not register subcommands")