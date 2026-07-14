"""CLI and output contract tests for the minimal ticket promote command,
normalized relationship JSON in ticket show/list --json, and absence of
duplicated artifact lifecycle status in strategy output.

Covers T11 requirements:
- CLI parser snapshot includes ticket promote with expected flags
- Parser correctly parses promote arguments
- Handler dispatches promote and produces structured output
- ticket show --json includes normalized epics with kind/provenance
- ticket list --json includes normalized epics with kind/provenance
- Strategy output does not duplicate artifact lifecycle status
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cli import build_parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(args: list[str]) -> argparse.Namespace:
    """Parse *args* through the megaplan CLI parser."""
    parser = build_parser()
    return parser.parse_args(args)


def _snapshot_subcommand(snapshot: dict, *path: str) -> dict:
    """Walk the parser snapshot dict to a subcommand node."""
    node = snapshot["commands"][""]
    for segment in path:
        node = node["subcommands"][segment]
    return node


# ---------------------------------------------------------------------------
# CLI parser — ticket promote
# ---------------------------------------------------------------------------


class TestTicketPromoteParser:
    """Verify the ticket promote subcommand is registered and parseable."""

    def test_promote_subcommand_registered_in_ticket(self) -> None:
        """``ticket promote`` must be a registered subcommand of ``ticket``."""
        parser = build_parser()
        # Find the ticket subparser
        ticket_action = None
        for action in parser._actions:
            if action.dest == "command" and isinstance(action, argparse._SubParsersAction):
                ticket_parser = action.choices.get("ticket")
                assert ticket_parser is not None, "ticket subcommand not found"
                # Find promote in ticket's subparsers
                for ta in ticket_parser._actions:
                    if ta.dest == "ticket_action" and isinstance(
                        ta, argparse._SubParsersAction
                    ):
                        ticket_action = ta
                        break
                break

        assert ticket_action is not None, "ticket_action subparser not found"
        assert (
            "promote" in ticket_action.choices
        ), "promote not registered under ticket subcommands"

    def test_promote_parses_ticket_id_positional(self) -> None:
        """The promote command accepts a required ticket_id positional."""
        args = _parse(["ticket", "promote", "01JNX0000001"])
        assert args.ticket_action == "promote"
        assert args.ticket_id == "01JNX0000001"

    def test_promote_parses_initiative_slug_flag(self) -> None:
        """``--initiative-slug`` sets an explicit initiative slug."""
        args = _parse(
            ["ticket", "promote", "01JNX0000001", "--initiative-slug", "my-init"]
        )
        assert args.initiative_slug == "my-init"

    def test_promote_parses_title_flag(self) -> None:
        """``--title`` sets an explicit epic title."""
        args = _parse(
            ["ticket", "promote", "01JNX0000001", "--title", "My Epic"]
        )
        assert args.title == "My Epic"

    def test_promote_parses_goal_flag(self) -> None:
        """``--goal`` sets an explicit epic goal."""
        args = _parse(
            ["ticket", "promote", "01JNX0000001", "--goal", "Achieve X"]
        )
        assert args.goal == "Achieve X"

    def test_promote_parses_body_flag(self) -> None:
        """``--body`` sets an explicit epic body."""
        args = _parse(
            ["ticket", "promote", "01JNX0000001", "--body", "# Body"]
        )
        assert args.body == "# Body"

    def test_promote_parses_no_resolve_flag(self) -> None:
        """``--no-resolve`` is a store_true flag (defaults False)."""
        args_default = _parse(["ticket", "promote", "01JNX0000001"])
        assert args_default.no_resolve is False

        args_set = _parse(
            ["ticket", "promote", "01JNX0000001", "--no-resolve"]
        )
        assert args_set.no_resolve is True

    def test_promote_parses_skip_strategy_flag(self) -> None:
        """``--skip-strategy`` is a store_true flag (defaults False)."""
        args_default = _parse(["ticket", "promote", "01JNX0000001"])
        assert args_default.skip_strategy is False

        args_set = _parse(
            ["ticket", "promote", "01JNX0000001", "--skip-strategy"]
        )
        assert args_set.skip_strategy is True

    def test_promote_parses_json_flag(self) -> None:
        """``--json`` enables machine-readable output."""
        args_default = _parse(["ticket", "promote", "01JNX0000001"])
        assert args_default.json is False

        args_set = _parse(
            ["ticket", "promote", "01JNX0000001", "--json"]
        )
        assert args_set.json is True

    def test_promote_parses_all_flags_combined(self) -> None:
        """All promote flags can be combined in a single invocation."""
        args = _parse(
            [
                "ticket",
                "promote",
                "01JNX0000001",
                "--initiative-slug", "my-slug",
                "--title", "My Epic Title",
                "--goal", "My Goal",
                "--body", "Epic body text",
                "--no-resolve",
                "--skip-strategy",
                "--json",
            ]
        )
        assert args.ticket_id == "01JNX0000001"
        assert args.initiative_slug == "my-slug"
        assert args.title == "My Epic Title"
        assert args.goal == "My Goal"
        assert args.body == "Epic body text"
        assert args.no_resolve is True
        assert args.skip_strategy is True
        assert args.json is True

    def test_promote_missing_ticket_id_is_error(self) -> None:
        """Omitting the required ticket_id positional should raise SystemExit."""
        with pytest.raises(SystemExit):
            _parse(["ticket", "promote"])


# ---------------------------------------------------------------------------
# Parser snapshot — ticket promote presence
# ---------------------------------------------------------------------------


class TestParserSnapshotPromote:
    """Verify the parser snapshot fixture includes the ticket promote subcommand."""

    @pytest.fixture
    def fixture_data(self) -> dict[str, Any]:
        fixture_path = (
            Path(__file__).resolve().parent.parent.parent
            / "fixtures" / "cli_parser_snapshot.json"
        )
        if not fixture_path.exists():
            pytest.skip("Snapshot fixture not yet generated")
        return json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_snapshot_includes_ticket_promote(self, fixture_data) -> None:
        """The snapshot must include ``ticket → promote``."""
        promote = _snapshot_subcommand(fixture_data, "ticket", "promote")
        assert promote, "ticket promote missing from parser snapshot"

    def test_snapshot_promote_has_ticket_id_positional(self, fixture_data) -> None:
        """promote must have a positional for ticket_id."""
        promote = _snapshot_subcommand(fixture_data, "ticket", "promote")
        positionals = promote.get("positionals", [])
        ticket_id_pos = [
            p for p in positionals if p["dest"] == "ticket_id"
        ]
        assert len(ticket_id_pos) == 1, (
            f"Expected exactly one ticket_id positional, got {ticket_id_pos}"
        )

    def test_snapshot_promote_has_expected_options(self, fixture_data) -> None:
        """promote must have the expected option flags."""
        promote = _snapshot_subcommand(fixture_data, "ticket", "promote")
        option_dests = {o["dest"] for o in promote.get("options", [])}
        expected = {
            "initiative_slug",
            "title",
            "goal",
            "body",
            "no_resolve",
            "skip_strategy",
            "json",
        }
        missing = expected - option_dests
        assert not missing, f"Missing promote options: {sorted(missing)}"

        # Verify --no-resolve and --skip-strategy are boolean flags (nargs=0)
        for flag_dest in ("no_resolve", "skip_strategy", "json"):
            flag_opt = next(
                o for o in promote["options"] if o["dest"] == flag_dest
            )
            assert flag_opt["nargs"] == "0", (
                f"{flag_dest} should be store_true (nargs=0), "
                f"got nargs={flag_opt['nargs']!r}"
            )

    def test_snapshot_promote_has_no_extra_options(self, fixture_data) -> None:
        """promote must not accidentally broaden its CLI surface."""
        promote = _snapshot_subcommand(fixture_data, "ticket", "promote")
        option_dests = {o["dest"] for o in promote.get("options", [])}
        # -h/--help is always present
        allowed = {
            "help",
            "initiative_slug",
            "title",
            "goal",
            "body",
            "no_resolve",
            "skip_strategy",
            "json",
        }
        extra = option_dests - allowed
        assert not extra, (
            f"Unexpected promote options (surface drift): {sorted(extra)}"
        )


# ---------------------------------------------------------------------------
# Handler dispatch — ticket promote is wired
# ---------------------------------------------------------------------------


class TestTicketPromoteHandlerWiring:
    """Verify the promote handler is registered in the dispatch table."""

    def test_promote_in_ticket_dispatch(self) -> None:
        """``promote`` must be a key in TICKET_DISPATCH."""
        from arnold_pipelines.megaplan.handlers.tickets import TICKET_DISPATCH

        assert "promote" in TICKET_DISPATCH, (
            "promote handler not registered in TICKET_DISPATCH"
        )

    def test_promote_handler_callable(self) -> None:
        """The promote dispatch entry must be a callable."""
        from arnold_pipelines.megaplan.handlers.tickets import TICKET_DISPATCH

        handler = TICKET_DISPATCH.get("promote")
        assert handler is not None
        assert callable(handler)

    def test_promote_handler_is_handle_ticket_promote(self) -> None:
        """The promote dispatch entry is exactly ``handle_ticket_promote``."""
        from arnold_pipelines.megaplan.handlers.tickets import (
            TICKET_DISPATCH,
            handle_ticket_promote,
        )

        assert TICKET_DISPATCH["promote"] is handle_ticket_promote


# ---------------------------------------------------------------------------
# Output contracts — ticket show/list --json with normalized epics
# ---------------------------------------------------------------------------


class TestTicketShowJsonEpics:
    """Verify ``ticket show --json`` includes normalized epics fields."""

    def _write_ticket(self, repo: Path, ticket_id: str, title: str,
                      epics: list[dict] | None = None) -> Path:
        """Write a minimal ticket markdown file."""
        tickets_dir = repo / ".megaplan" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        from arnold_pipelines.megaplan.tickets.files import slugify

        slug = slugify(title)
        fpath = tickets_dir / f"{ticket_id}-{slug}.md"
        lines = [
            "---",
            f"id: {ticket_id}",
            f"title: {title}",
            "status: open",
            "source: human",
            "tags: []",
        ]
        if epics:
            # Write epics as YAML-like list
            lines.append("epics:")
            for ep in epics:
                lines.append(f"  - epic_id: {ep['epic_id']}")
                lines.append(f"    resolves_on_complete: {str(ep.get('resolves_on_complete', False)).lower()}")
                if "kind" in ep:
                    lines.append(f"    kind: {ep['kind']}")
                if "provenance" in ep and ep["provenance"] is not None:
                    lines.append(f"    provenance: {ep['provenance']}")
        lines.append("---")
        lines.append("")
        lines.append("Ticket body content.")
        fpath.write_text("\n".join(lines), encoding="utf-8")
        return fpath

    def test_show_json_includes_epics_with_kind_and_provenance(self, tmp_path: Path) -> None:
        """ticket show --json output must include epics with kind and provenance."""
        import io
        import sys

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo, capture_output=True,
        )
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=repo, capture_output=True,
        )

        # Write ticket with epics including kind and provenance
        self._write_ticket(
            repo,
            "01JNX000SHOW",
            "Show Test Ticket",
            epics=[
                {
                    "epic_id": "epic-one",
                    "resolves_on_complete": True,
                    "kind": "resolves_on_complete",
                    "provenance": "promotion:01JNX000SHOW",
                },
                {
                    "epic_id": "epic-two",
                    "resolves_on_complete": False,
                    "kind": "associated",
                    "provenance": None,
                },
            ],
        )

        # Capture stdout from show --json
        old_cwd = os.getcwd()
        try:
            os.chdir(repo)
            from arnold_pipelines.megaplan.tickets.core import show

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                show("01JNX000SHOW", json_output=True, cwd=repo)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()
            # Should be valid JSON
            result = json.loads(output)
        finally:
            os.chdir(old_cwd)

        assert "epics" in result, f"show --json must include epics key: {list(result.keys())}"
        epics = result["epics"]
        assert isinstance(epics, list)
        assert len(epics) == 2

        # Each epics entry must have kind and provenance
        for entry in epics:
            assert "kind" in entry, f"epics entry missing kind: {entry}"
            assert entry["kind"] in {
                "associated", "resolves_on_complete", "promoted_to_epic",
            }, f"unexpected kind: {entry['kind']}"
            assert "provenance" in entry, f"epics entry missing provenance: {entry}"

    def test_show_json_with_legacy_epics_normalized(self, tmp_path: Path) -> None:
        """Legacy epics (no kind/provenance) normalize in show --json output."""
        import io
        import sys

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo, capture_output=True,
        )
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=repo, capture_output=True,
        )

        # Write ticket with legacy epics (no kind/provenance)
        self._write_ticket(
            repo,
            "01JNX000LEGACY",
            "Legacy Test Ticket",
            epics=[
                {
                    "epic_id": "old-epic",
                    "resolves_on_complete": True,
                    # No kind, no provenance — legacy
                },
            ],
        )

        old_cwd = os.getcwd()
        try:
            os.chdir(repo)
            from arnold_pipelines.megaplan.tickets.core import show

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                show("01JNX000LEGACY", json_output=True, cwd=repo)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()
            result = json.loads(output)
        finally:
            os.chdir(old_cwd)

        assert "epics" in result
        epics = result["epics"]
        assert len(epics) == 1
        entry = epics[0]
        # Legacy normalizes to kind=resolves_on_complete
        assert entry["kind"] == "resolves_on_complete"
        assert entry["provenance"] is None
        assert entry["epic_id"] == "old-epic"
        assert entry["resolves_on_complete"] is True


class TestTicketListJsonEpics:
    """Verify ``ticket list --json`` includes normalized epics fields."""

    def _write_ticket(self, repo: Path, ticket_id: str, title: str,
                      epics: list[dict] | None = None) -> Path:
        """Write a minimal ticket markdown file."""
        tickets_dir = repo / ".megaplan" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        from arnold_pipelines.megaplan.tickets.files import slugify

        slug = slugify(title)
        fpath = tickets_dir / f"{ticket_id}-{slug}.md"
        lines = [
            "---",
            f"id: {ticket_id}",
            f"title: {title}",
            "status: open",
            "source: human",
            "tags: []",
        ]
        if epics:
            lines.append("epics:")
            for ep in epics:
                lines.append(f"  - epic_id: {ep['epic_id']}")
                lines.append(f"    resolves_on_complete: {str(ep.get('resolves_on_complete', False)).lower()}")
                if "kind" in ep:
                    lines.append(f"    kind: {ep['kind']}")
                if "provenance" in ep and ep["provenance"] is not None:
                    lines.append(f"    provenance: {ep['provenance']}")
        lines.append("---")
        lines.append("")
        lines.append("Ticket body content.")
        fpath.write_text("\n".join(lines), encoding="utf-8")
        return fpath

    def test_list_json_includes_epics_with_kind_and_provenance(self, tmp_path: Path) -> None:
        """ticket list --json output must include epics with kind and provenance."""
        import io
        import sys

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo, capture_output=True,
        )
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=repo, capture_output=True,
        )

        # Write ticket with epics
        self._write_ticket(
            repo,
            "01JNX000LIST",
            "List Test Ticket",
            epics=[
                {
                    "epic_id": "list-epic",
                    "resolves_on_complete": False,
                    "kind": "associated",
                    "provenance": None,
                },
            ],
        )

        old_cwd = os.getcwd()
        try:
            os.chdir(repo)
            from arnold_pipelines.megaplan.tickets.core import list_tickets

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                list_tickets(json_output=True, cwd=repo)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()
            results = json.loads(output)
        finally:
            os.chdir(old_cwd)

        assert isinstance(results, list)
        assert len(results) >= 1

        # Find our ticket
        ticket = next(
            (t for t in results if t["id"] == "01JNX000LIST"), None
        )
        assert ticket is not None, "Ticket not in list output"

        assert "epics" in ticket, (
            f"list --json must include epics: {list(ticket.keys())}"
        )
        epics = ticket["epics"]
        assert isinstance(epics, list)
        assert len(epics) == 1
        entry = epics[0]
        assert "kind" in entry
        assert entry["kind"] == "associated"
        assert "provenance" in entry

    def test_ticket_show_does_not_include_strategy_status(self, tmp_path: Path) -> None:
        """ticket show --json must NOT include strategy/roadmap lifecycle status fields.

        The ticket output should be about the ticket artifact only, not about
        where it sits on a strategy roadmap.
        """
        import io
        import sys

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo, capture_output=True,
        )
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=repo, capture_output=True,
        )

        self._write_ticket(
            repo,
            "01JNX000NOSTRAT",
            "No Strategy Status",
            epics=[
                {
                    "epic_id": "some-epic",
                    "resolves_on_complete": False,
                    "kind": "associated",
                    "provenance": None,
                },
            ],
        )

        old_cwd = os.getcwd()
        try:
            os.chdir(repo)
            from arnold_pipelines.megaplan.tickets.core import show

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                show("01JNX000NOSTRAT", json_output=True, cwd=repo)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()
            result = json.loads(output)
        finally:
            os.chdir(old_cwd)

        # Strategy/roadmap lifecycle fields must NOT be present
        forbidden = {
            "horizon",
            "roadmap_status",
            "strategy_phase",
            "lifecycle_state",
            "epic_status",
            "strategy_entry",
            "roadmap",
        }
        present_forbidden = forbidden & set(result.keys())
        assert not present_forbidden, (
            f"ticket show --json must not include strategy lifecycle fields: "
            f"{sorted(present_forbidden)}"
        )

    def test_ticket_list_does_not_include_strategy_status(self, tmp_path: Path) -> None:
        """ticket list --json must NOT include strategy/roadmap lifecycle status fields."""
        import io
        import sys

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo, capture_output=True,
        )
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=repo, capture_output=True,
        )

        self._write_ticket(repo, "01JNX000LIST2", "List No Strategy")

        old_cwd = os.getcwd()
        try:
            os.chdir(repo)
            from arnold_pipelines.megaplan.tickets.core import list_tickets

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                list_tickets(json_output=True, cwd=repo)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()
            results = json.loads(output)
        finally:
            os.chdir(old_cwd)

        for ticket in results:
            forbidden = {
                "horizon",
                "roadmap_status",
                "strategy_phase",
                "lifecycle_state",
                "epic_status",
                "strategy_entry",
                "roadmap",
            }
            present_forbidden = forbidden & set(ticket.keys())
            assert not present_forbidden, (
                f"ticket list --json entry must not include strategy lifecycle "
                f"fields: {sorted(present_forbidden)} in ticket {ticket.get('id')}"
            )


# ---------------------------------------------------------------------------
# Strategy output — no duplicated artifact lifecycle status
# ---------------------------------------------------------------------------


class TestStrategyOutputNoLifecycleDuplication:
    """Verify strategy output does not duplicate artifact lifecycle status."""

    def test_serialize_strategy_produces_no_status_fields(self) -> None:
        """serialize_strategy output must not contain per-ticket status fields."""
        from arnold_pipelines.megaplan.strategy.parser import serialize_strategy
        from arnold_pipelines.megaplan.strategy.contract import (
            RoadmapEntry,
            SourceLocation,
            StrategyDocument,
            StrategyIdentity,
            StrategySection,
        )

        doc = StrategyDocument(
            schema_version="1.0.0",
            stable_direction=[
                StrategySection(
                    title="Context",
                    body="Test context.",
                    source_location=SourceLocation(
                        path="STRATEGY.md", line=5, column=1
                    ),
                ),
            ],
            roadmap={
                "Now": [
                    RoadmapEntry(
                        identity=StrategyIdentity(type="epic", ref="epic-slug"),
                        display_title="My Epic",
                        horizon="Now",
                        source_location=SourceLocation(
                            path="STRATEGY.md", line=42, column=1
                        ),
                    ),
                ],
            },
            diagnostics=[],
        )

        serialized = serialize_strategy(doc)

        # The serialized markdown must not contain lifecycle status fields
        forbidden_patterns = [
            "status:",
            "lifecycle:",
            "artifact_status:",
            "ticket_status:",
            "epic_status:",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in serialized.lower(), (
                f"serialized strategy must not contain '{pattern}'. "
                f"Found in: ...{serialized[max(0, serialized.lower().find(pattern)-20):serialized.lower().find(pattern)+len(pattern)+20]}..."
            )

    def test_add_roadmap_entry_does_not_embed_status(self) -> None:
        """Adding a roadmap entry must not embed artifact lifecycle status in strategy."""
        from arnold_pipelines.megaplan.strategy.mutations import add_roadmap_entry
        from arnold_pipelines.megaplan.strategy.parser import serialize_strategy
        from arnold_pipelines.megaplan.strategy.contract import (
            RoadmapEntry,
            SourceLocation,
            StrategyDocument,
            StrategyIdentity,
            StrategySection,
        )

        doc = StrategyDocument(
            schema_version="1.0.0",
            stable_direction=[
                StrategySection(
                    title="Context",
                    body="Test context.",
                    source_location=SourceLocation(
                        path="STRATEGY.md", line=5, column=1
                    ),
                ),
            ],
            roadmap={"Now": [], "Next": [], "Later": []},
            diagnostics=[],
        )

        entry = RoadmapEntry(
            identity=StrategyIdentity(type="epic", ref="test-entry"),
            display_title="Test Entry",
            horizon="Now",
            source_location=SourceLocation(
                path="STRATEGY.md", line=42, column=1
            ),
        )

        updated = add_roadmap_entry(
            doc, entry, horizon="Now"
        )

        serialized = serialize_strategy(updated)

        # Must contain the entry identity ref
        assert "test-entry" in serialized

        # Must not contain lifecycle status
        forbidden = ["status:", "lifecycle:", "artifact_status:"]
        for pattern in forbidden:
            assert pattern not in serialized.lower(), (
                f"strategy after add must not contain '{pattern}'"
            )

    def test_promotion_result_strategy_diagnostics_are_structured(self) -> None:
        """PromotionResult.strategy_diagnostics must be structured,
        not duplicated artifact status."""
        import dataclasses

        from arnold_pipelines.megaplan.tickets.promotion import PromotionResult
        from arnold_pipelines.megaplan.schemas import Epic
        from arnold_pipelines.megaplan.strategy.contract import (
            SourceLocation,
            StrategyDiagnostic,
        )

        epic = Epic(
            id="test-epic",
            title="Test",
            goal="A goal",
            body="",
            state="shaping",
        )

        diag = StrategyDiagnostic(
            level="warning",
            message="test diagnostic",
            source_location=SourceLocation(path="STRATEGY.md", line=1, column=1),
        )

        result = PromotionResult(
            ticket_id="01JNX0000001",
            initiative_slug="test-init",
            epic=epic,
            link=None,
            initiative_created=True,
            epic_created=True,
            strategy_updated=False,
            strategy_diagnostics=[diag],
        )

        d = dataclasses.asdict(result)
        assert d["strategy_updated"] is False
        assert isinstance(d["strategy_diagnostics"], list)
        assert len(d["strategy_diagnostics"]) == 1
        assert d["strategy_diagnostics"][0]["level"] == "warning"
        assert d["strategy_diagnostics"][0]["message"] == "test diagnostic"

        # Diagnostics must not carry status fields
        for diag_dict in d["strategy_diagnostics"]:
            forbidden = {"status", "lifecycle", "artifact_status", "code"}
            present = forbidden & set(diag_dict.keys())
            assert not present, (
                f"strategy_diagnostic must not carry {sorted(present)}"
            )

    def test_sense_check_sc11_narrow_promote_surface(self) -> None:
        """SC11: CLI/parser/output tests lock the narrow promote command
        and normalized relationship JSON without expanding into full
        strategy authoring UX.

        This test verifies that promote does NOT add strategy-authoring
        options (like --horizon, --strategy-section, --roadmap-position)
        that would leak into full strategy editing.
        """
        # Verify parser surface is narrow
        promote = _snapshot_subcommand(
            json.loads(
                (
                    Path(__file__).resolve().parent.parent.parent
                    / "fixtures" / "cli_parser_snapshot.json"
                ).read_text(encoding="utf-8")
            ),
            "ticket",
            "promote",
        )
        option_dests = {o["dest"] for o in promote.get("options", [])}

        # These would indicate strategy-authoring scope creep
        forbidden_options = {
            "horizon",
            "strategy_section",
            "roadmap_position",
            "strategy_phase",
            "milestone",
            "target_horizon",
            "after_entry",
            "before_entry",
        }
        present = forbidden_options & option_dests
        assert not present, (
            f"promote must not expand into strategy authoring UX. "
            f"Forbidden options detected: {sorted(present)}"
        )

        # Verify the allowed set is exactly what T10 shipped
        allowed = {
            "help",
            "initiative_slug",
            "title",
            "goal",
            "body",
            "no_resolve",
            "skip_strategy",
            "json",
        }
        extra = option_dests - allowed
        assert not extra, f"Unexpected promote options: {sorted(extra)}"
