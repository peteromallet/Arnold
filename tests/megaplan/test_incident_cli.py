"""CLI tests for ``megaplan incident`` commands.

Exercises ``list --active`` against a fixture ledger, ``brief <id-or-session>``
bounded JSON output, clean unknown-id failure, and a regression assertion that
a representative non-incident CLI command still follows the existing path.
"""

from __future__ import annotations

import argparse
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident import IncidentLedger
from arnold_pipelines.megaplan.incident.cli import (
    register_incident_subcommands,
    run_incident_cli,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": 1,
        "event_id": "evt-a1",
        "ts": "2026-07-03T18:00:00Z",
        "scope": "repair_system",
        "outcome": "started",
        "incident_id": "inc-alpha",
        "type": "detection",
        "actor": "watchdog",
        "summary": "Build runner failed on startup",
        "evidence": [{"kind": "file", "path": "logs/runner.log"}],
        "next_expected_event": "immediate_repair.repair_attempt",
        "deadline_ts": "2026-07-03T20:00:00Z",
        "parent_event_ids": [],
        "trigger_event_id": None,
        "session_id": "session-alpha",
        "problem_id": "prob-alpha",
    }
    event.update(overrides)
    return event


def _terminal_event(**overrides: object) -> dict[str, object]:
    return _event(
        incident_id="inc-closed",
        type="closed",
        actor="commander",
        ts="2026-07-03T19:00:00Z",
        summary="Closed the incident",
        evidence=[],
        parent_event_ids=["evt-a1"],
        event_id="evt-closed",
        outcome="resolved",
        next_expected_event=None,
        session_id="session-closed",
        problem_id="prob-closed",
        **overrides,
    )


def _build_incident_parser() -> argparse.ArgumentParser:
    """Return a fully registered incident sub-command parser."""
    parser = argparse.ArgumentParser(prog="megaplan incident")
    register_incident_subcommands(parser)
    return parser


# ---------------------------------------------------------------------------
# list --active
# ---------------------------------------------------------------------------


def test_list_active_returns_active_incidents_in_stable_json(
    tmp_path: Path,
) -> None:
    """``list --active`` should emit only non-terminal incidents as JSON."""
    _populate_active_and_terminal_ledger(tmp_path)

    parser = _build_incident_parser()
    args = parser.parse_args(["list", "--active"])

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args))

    result = json.loads(stdout.getvalue())
    assert isinstance(result, list)
    assert len(result) >= 1
    ids = {inc["incident_id"] for inc in result}
    assert "inc-alpha" in ids
    # Terminal incident must *not* appear when active_only=True.
    assert "inc-closed" not in ids


def test_list_all_shows_terminal_incidents(tmp_path: Path) -> None:
    """``list --all`` should include terminal incidents."""
    _populate_active_and_terminal_ledger(tmp_path)

    parser = _build_incident_parser()
    args = parser.parse_args(["list", "--all"])

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args))

    result = json.loads(stdout.getvalue())
    assert isinstance(result, list)
    ids = {inc["incident_id"] for inc in result}
    assert ids == {"inc-alpha", "inc-closed"}


# ---------------------------------------------------------------------------
# brief <id-or-session>
# ---------------------------------------------------------------------------


def test_brief_by_incident_id_returns_bounded_json(tmp_path: Path) -> None:
    """Brief resolved by incident_id should return a bounded JSON shape."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())

    parser = _build_incident_parser()
    args = parser.parse_args(["brief", "inc-alpha"])

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args))

    brief = json.loads(stdout.getvalue())
    assert brief["found"] is True
    assert brief["incident_id"] == "inc-alpha"
    assert "state" in brief
    assert "outcome" in brief
    assert "summary" in brief
    assert "latest_actor" in brief
    assert "next_expected_event" in brief
    assert "deadline_ts" in brief
    assert "event_count" in brief
    assert "first_timestamp" in brief
    assert "last_timestamp" in brief
    assert "claims" in brief
    assert "evidence" in brief
    assert "attempts" in brief
    assert "placeholders" in brief
    assert "integrity" in brief


def test_brief_by_session_id_resolves_same_incident(tmp_path: Path) -> None:
    """Brief resolved by session_id should return the same incident as by id."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())

    parser = _build_incident_parser()
    args_by_id = parser.parse_args(["brief", "inc-alpha"])
    args_by_session = parser.parse_args(["brief", "session-alpha"])

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args_by_id))
    brief_by_id = json.loads(stdout.getvalue())

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args_by_session))
    brief_by_session = json.loads(stdout.getvalue())

    assert brief_by_id["found"] is True
    assert brief_by_session["found"] is True
    assert brief_by_id["incident_id"] == brief_by_session["incident_id"]


def test_brief_unknown_id_returns_not_found_with_integrity(tmp_path: Path) -> None:
    """Brief for an unknown id should return ``found: false`` cleanly."""
    parser = _build_incident_parser()
    args = parser.parse_args(["brief", "nonexistent"])

    stdout = StringIO()
    exit_code = _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args))

    brief = json.loads(stdout.getvalue())
    assert brief["found"] is False
    assert brief["query"] == "nonexistent"
    assert "integrity" in brief
    assert exit_code == 0


def test_brief_output_is_stable_json(tmp_path: Path) -> None:
    """Brief output should be stable JSON with deterministic key ordering."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())

    parser = _build_incident_parser()
    args = parser.parse_args(["brief", "inc-alpha"])

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args))
    first = stdout.getvalue()

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args))
    second = stdout.getvalue()

    assert first == second


def test_brief_with_now_classifies_deadline(tmp_path: Path) -> None:
    """Brief with ``--now`` should emit ``deadline_status``."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event(deadline_ts="2026-07-03T20:00:00Z"))

    parser = _build_incident_parser()
    args = parser.parse_args(["brief", "inc-alpha", "--now", "2026-07-03T21:00:00Z"])

    stdout = StringIO()
    _with_stdout(stdout, lambda: run_incident_cli(tmp_path, args))

    brief = json.loads(stdout.getvalue())
    assert brief["found"] is True
    assert "deadline_status" in brief
    # now > deadline → overdue
    assert brief["deadline_status"] == "overdue"


# ---------------------------------------------------------------------------
# Regression: non-incident dispatch still works
# ---------------------------------------------------------------------------


def test_non_incident_command_still_dispatches_to_existing_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A representative non-incident CLI command must still follow the
    existing dispatch path (no regression from the incident branch)."""
    from arnold_pipelines.megaplan.cli import main as megaplan_main

    # We call the megaplan main entrypoint with a harmless subcommand that
    # falls through to the existing parser.  The incident early-return branch
    # must NOT swallow a non-incident argv.
    captured: list[int] = []

    def fake_exit(code: int) -> None:
        captured.append(code)

    monkeypatch.setattr(sys, "exit", fake_exit)
    # Use --help to avoid any side effects (no real state mutation).
    megaplan_main(["--help"])
    # If the incident branch incorrectly intercepted, argparse would fail
    # with an "unknown command" error; reaching here means the existing
    # path was preserved.
    assert len(captured) > 0
    # argparse exits 0 for --help.
    assert captured[0] == 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _populate_active_and_terminal_ledger(root: Path) -> None:
    """Write one active and one terminal incident event into the ledger."""
    ledger = IncidentLedger(root)
    ledger.append_event(_event())
    ledger.append_event(_terminal_event())


def _with_stdout(buf: StringIO, fn) -> int:
    """Redirect sys.stdout to *buf*, run *fn*, restore, return fn's result."""
    old = sys.stdout
    sys.stdout = buf
    try:
        return fn()
    finally:
        sys.stdout = old
