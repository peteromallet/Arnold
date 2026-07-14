"""Tests for strategy migration inspection (T7).

Covers the migration doctor contract:
- inspect_strategy_migration() return shape
- absent strategy → valid unadopted state (ok, safe_to_apply=False)
- current version with clean inventory → ok
- legacy/missing/unsupported version → findings + actions
- malformed strategy → blocked
- ticket identity inventory integration (duplicate IDs, invalid ULIDs, legacy filenames)
- Store advisory integration (None store, store with links)
- No files are written by the inspection
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.strategy.migration import (
    ACTION_ADD_FRONTMATTER_ID,
    ACTION_FIX_INVALID_FILENAME,
    ACTION_FIX_PARSE_ERROR,
    ACTION_RENAME_FILE,
    ACTION_RESOLVE_DUPLICATE,
    ACTION_UPGRADE_VERSION,
    FINDING_DUPLICATE_IDS,
    FINDING_INVALID_FILENAME_ULID,
    FINDING_INVALID_ULID,
    FINDING_LEGACY_FILENAME,
    FINDING_MISSING_ID,
    FINDING_NO_TICKETS_DIR,
    FINDING_PARSE_ERROR,
    FINDING_ROADMAP_ORPHAN,
    FINDING_STRATEGY_ABSENT,
    FINDING_TICKETS_PRESENT,
    FINDING_VERSION_CURRENT,
    FINDING_VERSION_LEGACY,
    FINDING_VERSION_MALFORMED,
    FINDING_VERSION_MISSING,
    FINDING_VERSION_UNSUPPORTED_NEW,
    FINDING_VERSION_UNSUPPORTED_OLD,
    MigrationAction,
    MigrationFinding,
    MigrationReport,
    inspect_strategy_migration,
)
from arnold_pipelines.megaplan.strategy.versions import CURRENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal repo root under tmp_path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _write_strategy(repo: Path, content: str) -> Path:
    """Write .megaplan/STRATEGY.md and return its path."""
    md = repo / ".megaplan"
    md.mkdir(parents=True, exist_ok=True)
    path = md / "STRATEGY.md"
    path.write_text(content, encoding="utf-8")
    return path


def _make_tickets_dir(repo: Path) -> Path:
    """Create .megaplan/tickets/ and return its path."""
    td = repo / ".megaplan" / "tickets"
    td.mkdir(parents=True, exist_ok=True)
    return td


def _write_ticket(td: Path, filename: str, content: str) -> Path:
    """Write a synthetic ticket file."""
    path = td / filename
    path.write_text(content, encoding="utf-8")
    return path


def _valid_ulid() -> str:
    return "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _valid_ulid_2() -> str:
    return "01ARZ3NDEKTSV4RRFFQ69G5FAW"


def _minimal_ticket(uid: str, title: str = "Test Ticket") -> str:
    return (
        "---\n"
        f"id: {uid}\n"
        f"title: {title}\n"
        "status: open\n"
        "---\n"
        "\n"
        "Ticket body.\n"
    )


def _minimal_strategy(schema_version: str = CURRENT_SCHEMA_VERSION,
                      ticket_refs: list[str] | None = None) -> str:
    refs = ""
    if ticket_refs:
        refs = "\n".join(f"- [ticket:{r}] Some ticket" for r in ticket_refs) + "\n"
    return (
        "---\n"
        f"schema_version: {schema_version}\n"
        "---\n"
        "\n"
        "## Mission\n\nTest.\n\n"
        "## Principles\n\nTest.\n\n"
        "## Architecture Direction\n\nTest.\n\n"
        "## Constraints\n\nTest.\n\n"
        "## Non-Goals\n\nTest.\n\n"
        "## Now\n\n"
        f"{refs}\n"
        "## Next\n\n\n"
        "## Later\n\n\n"
    )


def _minimal_strategy_with_epic(slug: str,
                                 schema_version: str = CURRENT_SCHEMA_VERSION) -> str:
    """Minimal strategy with an epic ref in Now."""
    return (
        "---\n"
        f"schema_version: {schema_version}\n"
        "---\n"
        "\n"
        "## Mission\n\nTest.\n\n"
        "## Principles\n\nTest.\n\n"
        "## Architecture Direction\n\nTest.\n\n"
        "## Constraints\n\nTest.\n\n"
        "## Non-Goals\n\nTest.\n\n"
        f"## Now\n\n- [epic:{slug}] Epic Display Title\n\n"
        "## Next\n\n\n"
        "## Later\n\n\n"
    )


def _minimal_strategy_with_epic_title(slug: str, title: str,
                                       schema_version: str = CURRENT_SCHEMA_VERSION) -> str:
    """Minimal strategy with an epic ref and a specific display title."""
    return (
        "---\n"
        f"schema_version: {schema_version}\n"
        "---\n"
        "\n"
        "## Mission\n\nTest.\n\n"
        "## Principles\n\nTest.\n\n"
        "## Architecture Direction\n\nTest.\n\n"
        "## Constraints\n\nTest.\n\n"
        "## Non-Goals\n\nTest.\n\n"
        f"## Now\n\n- [epic:{slug}] {title}\n\n"
        "## Next\n\n\n"
        "## Later\n\n\n"
    )


def _minimal_strategy_with_ticket_title(uid: str, title: str,
                                         schema_version: str = CURRENT_SCHEMA_VERSION) -> str:
    """Minimal strategy with a ticket ref and a specific display title."""
    return (
        "---\n"
        f"schema_version: {schema_version}\n"
        "---\n"
        "\n"
        "## Mission\n\nTest.\n\n"
        "## Principles\n\nTest.\n\n"
        "## Architecture Direction\n\nTest.\n\n"
        "## Constraints\n\nTest.\n\n"
        "## Non-Goals\n\nTest.\n\n"
        f"## Now\n\n- [ticket:{uid}] {title}\n\n"
        "## Next\n\n\n"
        "## Later\n\n\n"
    )


def _create_initiative_dir(repo: Path, slug: str, *, title: str) -> Path:
    """Create a minimal initiative directory with README.md."""
    init_dir = repo / ".megaplan" / "initiatives" / slug
    init_dir.mkdir(parents=True)
    readme = init_dir / "README.md"
    readme.write_text(f"# {title}\n\nDescription text.\n", encoding="utf-8")
    return init_dir


def _write_projection(repo: Path) -> None:
    """Build and write a valid strategy projection from the current STRATEGY.md."""
    # Use load_strategy + write_strategy_projection.
    from arnold_pipelines.megaplan.strategy.io import load_strategy
    from arnold_pipelines.megaplan.strategy.projection import write_strategy_projection

    doc = load_strategy(str(repo))
    write_strategy_projection(doc, str(repo))


# ---------------------------------------------------------------------------
# Report shape contract
# ---------------------------------------------------------------------------


class TestMigrationReportShape:
    """The MigrationReport dataclass has all required fields."""

    def test_report_has_required_fields(self) -> None:
        report = MigrationReport(
            status="ok",
            version_status="absent",
            schema_version=None,
            current_version=CURRENT_SCHEMA_VERSION,
            ticket_inventory=None,
        )
        assert report.status == "ok"
        assert report.version_status == "absent"
        assert report.schema_version is None
        assert report.current_version == CURRENT_SCHEMA_VERSION
        assert report.ticket_inventory is None
        assert report.findings == []
        assert report.blockers == []
        assert report.proposed_actions == []
        assert report.safe_to_apply is False
        assert report.tickets_dir_exists is False
        assert isinstance(report.strategy_file_path, str)

    def test_migration_finding_fields(self) -> None:
        f = MigrationFinding(
            kind="test-kind",
            severity="info",
            message="test message",
            source="/some/path",
        )
        assert f.kind == "test-kind"
        assert f.severity == "info"
        assert f.message == "test message"
        assert f.source == "/some/path"

    def test_migration_finding_source_optional(self) -> None:
        f = MigrationFinding(kind="x", severity="warning", message="m")
        assert f.source is None

    def test_migration_action_fields(self) -> None:
        a = MigrationAction(
            action_id="act-1",
            kind="upgrade-version",
            description="Upgrade version.",
            target="/some/path",
            safe=True,
        )
        assert a.action_id == "act-1"
        assert a.kind == "upgrade-version"
        assert a.description == "Upgrade version."
        assert a.target == "/some/path"
        assert a.safe is True

    def test_migration_action_default_safe(self) -> None:
        a = MigrationAction(action_id="a", kind="k", description="d")
        assert a.safe is True


# ---------------------------------------------------------------------------
# Absent strategy — valid unadopted state
# ---------------------------------------------------------------------------


class TestAbsentStrategy:
    """Absent .megaplan/STRATEGY.md is a valid unadopted state."""

    def test_absent_strategy_status_ok(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        assert report.status == "ok"
        assert report.version_status == "absent"
        assert report.safe_to_apply is False
        assert report.schema_version is None

    def test_absent_strategy_has_absent_finding(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        absent_findings = [f for f in report.findings if f.kind == FINDING_STRATEGY_ABSENT]
        assert len(absent_findings) == 1
        assert absent_findings[0].severity == "info"

    def test_absent_strategy_no_blockers(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        assert report.blockers == []

    def test_absent_strategy_no_actions(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        assert report.proposed_actions == []

    def test_absent_strategy_file_path_is_set(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        assert report.strategy_file_path.endswith(".megaplan/STRATEGY.md")

    def test_absent_strategy_no_tickets_dir_finding(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        no_td = [f for f in report.findings if f.kind == FINDING_NO_TICKETS_DIR]
        assert len(no_td) == 1


# ---------------------------------------------------------------------------
# Current version — clean
# ---------------------------------------------------------------------------


class TestCurrentVersion:
    """Current schema version with no ticket issues → ok."""

    def test_current_version_status_ok(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        assert report.status == "ok"
        assert report.version_status == "current"
        assert report.schema_version == CURRENT_SCHEMA_VERSION

    def test_current_version_has_current_finding(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        current = [f for f in report.findings if f.kind == FINDING_VERSION_CURRENT]
        assert len(current) == 1

    def test_current_version_no_blockers(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        assert report.blockers == []

    def test_current_version_no_actions(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        assert report.proposed_actions == []

    def test_current_version_safe_to_apply_false_when_nothing_to_do(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        assert report.safe_to_apply is False  # nothing to do


# ---------------------------------------------------------------------------
# Version status — legacy / missing / unsupported
# ---------------------------------------------------------------------------


class TestLegacyVersion:
    """Unrecognized older versions (not in LEGACY_VERSIONS) are blocked.

    The settled gate is that unknown pre-v1 versions have no safe, reversible
    upgrade path, so the inspector reports an error/blocker and never proposes
    an upgrade action. The apply path must therefore refuse to write.
    """

    def test_legacy_version_is_blocked(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(schema_version="megaplan-strategy-v0"))
        report = inspect_strategy_migration(repo)
        assert report.version_status == "unsupported-old"  # v0 not in LEGACY_VERSIONS
        assert report.status == "blocked"
        assert report.safe_to_apply is False

    def test_legacy_version_has_error_finding(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(schema_version="megaplan-strategy-v0"))
        report = inspect_strategy_migration(repo)
        findings = [f for f in report.findings
                     if f.kind == FINDING_VERSION_UNSUPPORTED_OLD]
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_legacy_version_has_blocker_and_no_upgrade_action(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(schema_version="megaplan-strategy-v0"))
        report = inspect_strategy_migration(repo)
        assert len(report.blockers) >= 1
        actions = [a for a in report.proposed_actions if a.kind == ACTION_UPGRADE_VERSION]
        assert actions == []


class TestMissingVersion:
    """Missing schema_version in frontmatter → warning + upgrade action."""

    def test_missing_version(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        content = (
            "---\n"
            "title: No Version\n"
            "---\n"
            "\n"
            "## Mission\n\nTest.\n\n"
            "## Principles\n\nTest.\n\n"
            "## Architecture Direction\n\nTest.\n\n"
            "## Constraints\n\nTest.\n\n"
            "## Non-Goals\n\nTest.\n\n"
            "## Now\n\n\n"
            "## Next\n\n\n"
            "## Later\n\n\n"
        )
        _write_strategy(repo, content)
        report = inspect_strategy_migration(repo)
        assert report.version_status == "missing-version"
        missing = [f for f in report.findings if f.kind == FINDING_VERSION_MISSING]
        assert len(missing) == 1
        actions = [a for a in report.proposed_actions if a.kind == ACTION_UPGRADE_VERSION]
        assert len(actions) == 1
        assert actions[0].safe is True


class TestUnsupportedNew:
    """Too-new version → blocked."""

    def test_unsupported_new(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(schema_version="megaplan-strategy-v99"))
        report = inspect_strategy_migration(repo)
        assert report.status == "blocked"
        assert report.version_status == "unsupported-new"
        new_f = [f for f in report.findings if f.kind == FINDING_VERSION_UNSUPPORTED_NEW]
        assert len(new_f) == 1
        assert len(report.blockers) >= 1


class TestMalformedStrategy:
    """Malformed strategy → blocked."""

    def test_malformed_strategy_blocked(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, "This is not valid YAML frontmatter.\n---\n")
        report = inspect_strategy_migration(repo)
        assert report.status == "blocked"
        assert report.version_status == "malformed"
        mal = [f for f in report.findings if f.kind == FINDING_VERSION_MALFORMED]
        assert len(mal) == 1
        assert len(report.blockers) >= 1


# ---------------------------------------------------------------------------
# Ticket inventory integration
# ---------------------------------------------------------------------------


class TestTicketInventoryIntegration:
    """Migration report integrates ticket inventory findings."""

    def test_no_tickets_dir_reports_info(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        no_td = [f for f in report.findings if f.kind == FINDING_NO_TICKETS_DIR]
        assert len(no_td) == 1
        assert no_td[0].severity == "info"

    def test_empty_tickets_dir(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        _make_tickets_dir(repo)
        report = inspect_strategy_migration(repo)
        present = [f for f in report.findings if f.kind == FINDING_TICKETS_PRESENT]
        assert len(present) >= 1

    def test_ticket_inventory_in_report(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(ticket_refs=[_valid_ulid()]))
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-test.md", _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo)
        assert report.ticket_inventory is not None
        assert report.ticket_inventory.total_files == 1

    def test_tickets_dir_exists_flag(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _make_tickets_dir(repo)
        report = inspect_strategy_migration(repo)
        assert report.tickets_dir_exists is True

    def test_tickets_dir_does_not_exist_flag(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        assert report.tickets_dir_exists is False


# ---------------------------------------------------------------------------
# Duplicate IDs → blocked
# ---------------------------------------------------------------------------


class TestDuplicateIds:
    """Duplicate frontmatter ULIDs are blockers."""

    def test_duplicate_ids_blocked(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(ticket_refs=[_valid_ulid()]))
        td = _make_tickets_dir(repo)
        uid = _valid_ulid()
        _write_ticket(td, f"{uid}-first.md", _minimal_ticket(uid, "First"))
        _write_ticket(td, f"{uid}-second.md", _minimal_ticket(uid, "Second"))
        report = inspect_strategy_migration(repo)
        assert report.status == "blocked"
        dup_findings = [f for f in report.findings if f.kind == FINDING_DUPLICATE_IDS]
        assert len(dup_findings) >= 1
        assert len(report.blockers) >= 1

    def test_duplicate_ids_generate_resolve_action(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        uid = _valid_ulid()
        _write_ticket(td, f"{uid}-a.md", _minimal_ticket(uid))
        _write_ticket(td, f"{uid}-b.md", _minimal_ticket(uid))
        report = inspect_strategy_migration(repo)
        actions = [a for a in report.proposed_actions if a.kind == ACTION_RESOLVE_DUPLICATE]
        assert len(actions) >= 1
        assert actions[0].safe is False  # requires manual resolution

    def test_unique_ids_not_blocked(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(
            ticket_refs=[_valid_ulid(), _valid_ulid_2()]
        ))
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-a.md", _minimal_ticket(_valid_ulid()))
        _write_ticket(td, f"{_valid_ulid_2()}-b.md", _minimal_ticket(_valid_ulid_2()))
        report = inspect_strategy_migration(repo)
        # unique IDs + current version → ok (or needs-migration for filename shape)
        assert report.status != "blocked"


# ---------------------------------------------------------------------------
# Missing frontmatter ID
# ---------------------------------------------------------------------------


class TestMissingFrontmatterId:
    """Tickets without frontmatter id get warning + add-id action."""

    def test_missing_id_generates_warning(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        content = (
            "---\n"
            "title: No ID\n"
            "status: open\n"
            "---\n"
            "\n"
            "Body.\n"
        )
        _write_ticket(td, "some-legacy-file.md", content)
        report = inspect_strategy_migration(repo)
        missing = [f for f in report.findings if f.kind == FINDING_MISSING_ID]
        assert len(missing) >= 1
        assert missing[0].severity == "warning"

    def test_missing_id_generates_add_action(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        _write_ticket(td, "legacy.md", "---\ntitle: X\nstatus: open\n---\n\nBody.\n")
        report = inspect_strategy_migration(repo)
        actions = [a for a in report.proposed_actions if a.kind == ACTION_ADD_FRONTMATTER_ID]
        assert len(actions) >= 1
        assert actions[0].safe is True


# ---------------------------------------------------------------------------
# Invalid ULID
# ---------------------------------------------------------------------------


class TestInvalidUlid:
    """Invalid frontmatter ULIDs are blockers."""

    def test_invalid_ulid_blocked(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        _write_ticket(td, "bad-id-ticket.md", _minimal_ticket("not-a-ulid"))
        report = inspect_strategy_migration(repo)
        assert report.status == "blocked"
        invalid = [f for f in report.findings if f.kind == FINDING_INVALID_ULID]
        assert len(invalid) >= 1
        assert invalid[0].severity == "error"


# ---------------------------------------------------------------------------
# Legacy / non-canonical filename
# ---------------------------------------------------------------------------


class TestLegacyFilename:
    """Non-canonical filenames with valid frontmatter ULID get rename action."""

    def test_legacy_filename_generates_rename_action(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(ticket_refs=[_valid_ulid()]))
        td = _make_tickets_dir(repo)
        # Non-canonical filename (no ULID prefix)
        _write_ticket(td, "legacy-ticket-name.md", _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo)
        legacy = [f for f in report.findings if f.kind == FINDING_LEGACY_FILENAME]
        assert len(legacy) >= 1
        assert legacy[0].severity == "warning"
        actions = [a for a in report.proposed_actions if a.kind == ACTION_RENAME_FILE]
        assert len(actions) >= 1

    def test_canonical_filename_no_rename_action(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(ticket_refs=[_valid_ulid()]))
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-canonical.md",
                       _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo)
        actions = [a for a in report.proposed_actions if a.kind == ACTION_RENAME_FILE]
        assert len(actions) == 0

    def test_invalid_ulid_filename_prefix(self, tmp_path: Path) -> None:
        """26-char prefix that's not a valid ULID."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(ticket_refs=[_valid_ulid()]))
        td = _make_tickets_dir(repo)
        # 26 chars containing 'I' (invalid in Crockford base32)
        bad_prefix = "01ARZ3NDEKTSV4RRFFQ69G5FAI"
        _write_ticket(td, f"{bad_prefix}-bad.md", _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo)
        invalid_fn = [f for f in report.findings if f.kind == FINDING_INVALID_FILENAME_ULID]
        assert len(invalid_fn) >= 1
        actions = [a for a in report.proposed_actions if a.kind == ACTION_FIX_INVALID_FILENAME]
        assert len(actions) >= 1


# ---------------------------------------------------------------------------
# Parse errors
# ---------------------------------------------------------------------------


class TestParseErrors:
    """Parse errors generate warning findings and fix actions."""

    def test_parse_error_generates_finding_and_action(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        # Missing closing --- fence
        content = "---\nid: bad\n"
        _write_ticket(td, "broken.md", content)
        report = inspect_strategy_migration(repo)
        parse_errs = [f for f in report.findings if f.kind == FINDING_PARSE_ERROR]
        assert len(parse_errs) >= 1
        assert parse_errs[0].severity == "warning"
        actions = [a for a in report.proposed_actions if a.kind == ACTION_FIX_PARSE_ERROR]
        assert len(actions) >= 1


# ---------------------------------------------------------------------------
# Roadmap orphans
# ---------------------------------------------------------------------------


class TestRoadmapOrphans:
    """Tickets not referenced in strategy roadmap are reported as info."""

    def test_roadmap_orphan_reported(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        # Strategy has no ticket refs
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-orphan.md",
                       _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo)
        orphans = [f for f in report.findings if f.kind == FINDING_ROADMAP_ORPHAN]
        assert len(orphans) >= 1
        assert orphans[0].severity == "info"

    def test_roadmap_ticket_not_orphan(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(ticket_refs=[_valid_ulid()]))
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-in-roadmap.md",
                       _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo)
        orphans = [f for f in report.findings if f.kind == FINDING_ROADMAP_ORPHAN]
        assert len(orphans) == 0


# ---------------------------------------------------------------------------
# Store integration (None store)
# ---------------------------------------------------------------------------


class TestStoreIntegration:
    """Store=None is handled gracefully."""

    def test_store_none_does_not_crash(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy(ticket_refs=[_valid_ulid()]))
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-t.md", _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo, store=None)
        assert report.status in ("ok", "needs-migration")

    def test_store_explicit_none(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo, store=None)
        assert report.status == "ok"


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


class TestNoMutation:
    """inspect_strategy_migration writes nothing to disk."""

    def test_absent_strategy_no_file_created(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        strategy_path = repo / ".megaplan" / "STRATEGY.md"
        assert not strategy_path.exists()
        inspect_strategy_migration(repo)
        assert not strategy_path.exists()

    def test_existing_strategy_not_modified(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        content = _minimal_strategy()
        path = _write_strategy(repo, content)
        original = path.read_text()
        inspect_strategy_migration(repo)
        assert path.read_text() == original

    def test_ticket_files_not_modified(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        p1 = _write_ticket(td, "a.md", _minimal_ticket(_valid_ulid()))
        p2 = _write_ticket(td, "b.md", _minimal_ticket(_valid_ulid_2()))
        orig1 = p1.read_text()
        orig2 = p2.read_text()
        inspect_strategy_migration(repo)
        assert p1.read_text() == orig1
        assert p2.read_text() == orig2

    def test_strategy_file_not_created_when_absent(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        strategy_path = repo / ".megaplan" / "STRATEGY.md"
        assert not strategy_path.exists()
        inspect_strategy_migration(repo)
        # megaplan dir should NOT be created
        megaplan_dir = repo / ".megaplan"
        assert not megaplan_dir.exists() or not strategy_path.exists()


# ---------------------------------------------------------------------------
# Epic reference diagnostics (T8)
# ---------------------------------------------------------------------------


class TestEpicRefDiagnostics:
    """Strategy epic refs are checked against .megaplan/initiatives/ dirs."""

    def test_missing_epic_ref_blocker(self, tmp_path: Path) -> None:
        """Epic ref with missing initiative directory is a blocker."""
        repo = _make_repo(tmp_path)
        content = _minimal_strategy_with_epic("nonexistent-epic")
        _write_strategy(repo, content)
        report = inspect_strategy_migration(repo)
        assert report.status == "blocked"
        missing = [f for f in report.findings
                    if f.kind == "missing-epic-ref"]
        assert len(missing) >= 1
        assert missing[0].severity == "error"

    def test_epic_ref_with_initiative_dir_no_blocker(self, tmp_path: Path) -> None:
        """Epic ref with existing initiative directory is not a blocker."""
        repo = _make_repo(tmp_path)
        slug = "my-initiative"
        _create_initiative_dir(repo, slug, title="My Initiative")
        content = _minimal_strategy_with_epic(slug)
        _write_strategy(repo, content)
        report = inspect_strategy_migration(repo)
        missing = [f for f in report.findings
                    if f.kind == "missing-epic-ref"]
        assert len(missing) == 0

    def test_ambiguous_epic_ref_no_readme(self, tmp_path: Path) -> None:
        """Initiative dir exists but README.md is missing → ambiguous."""
        repo = _make_repo(tmp_path)
        slug = "no-readme-init"
        init_dir = repo / ".megaplan" / "initiatives" / slug
        init_dir.mkdir(parents=True)
        content = _minimal_strategy_with_epic(slug)
        _write_strategy(repo, content)
        report = inspect_strategy_migration(repo)
        ambiguous = [f for f in report.findings
                      if f.kind == "ambiguous-epic-ref"]
        assert len(ambiguous) >= 1
        assert ambiguous[0].severity == "warning"

    def test_no_epic_refs_no_findings(self, tmp_path: Path) -> None:
        """Strategy with no epic refs produces no epic-related findings."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        epic_findings = [f for f in report.findings
                          if f.kind in ("missing-epic-ref", "ambiguous-epic-ref")]
        assert len(epic_findings) == 0


# ---------------------------------------------------------------------------
# Stale title diagnostics (T8)
# ---------------------------------------------------------------------------


class TestStaleTitleDiagnostics:
    """Strategy display titles compared to actual artifact titles."""

    def test_stale_ticket_title_reported(self, tmp_path: Path) -> None:
        """Ticket title in strategy differs from frontmatter title."""
        repo = _make_repo(tmp_path)
        uid = _valid_ulid()
        # Strategy has a different display title than the ticket frontmatter
        content = _minimal_strategy_with_ticket_title(uid, "Old Title")
        _write_strategy(repo, content)
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{uid}-t.md", _minimal_ticket(uid, "New Title"))
        report = inspect_strategy_migration(repo)
        stale = [f for f in report.findings if f.kind == "stale-title"]
        assert len(stale) >= 1
        assert stale[0].severity == "warning"
        assert "Old Title" in stale[0].message
        assert "New Title" in stale[0].message

    def test_matching_ticket_title_no_stale_finding(self, tmp_path: Path) -> None:
        """Matching titles produce no stale-title finding."""
        repo = _make_repo(tmp_path)
        uid = _valid_ulid()
        content = _minimal_strategy_with_ticket_title(uid, "Same Title")
        _write_strategy(repo, content)
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{uid}-t.md", _minimal_ticket(uid, "Same Title"))
        report = inspect_strategy_migration(repo)
        stale = [f for f in report.findings if f.kind == "stale-title"]
        assert len(stale) == 0

    def test_stale_epic_title_reported(self, tmp_path: Path) -> None:
        """Epic title in strategy differs from initiative README title."""
        repo = _make_repo(tmp_path)
        slug = "stale-epic"
        _create_initiative_dir(repo, slug, title="Actual Epic Title")
        content = _minimal_strategy_with_epic_title(slug, "Stale Epic Title")
        _write_strategy(repo, content)
        report = inspect_strategy_migration(repo)
        stale = [f for f in report.findings if f.kind == "stale-title"]
        assert len(stale) >= 1

    def test_matching_epic_title_no_stale_finding(self, tmp_path: Path) -> None:
        """Matching epic titles produce no stale-title finding."""
        repo = _make_repo(tmp_path)
        slug = "matching-epic"
        _create_initiative_dir(repo, slug, title="Matching Title")
        content = _minimal_strategy_with_epic_title(slug, "Matching Title")
        _write_strategy(repo, content)
        report = inspect_strategy_migration(repo)
        stale = [f for f in report.findings if f.kind == "stale-title"]
        assert len(stale) == 0


# ---------------------------------------------------------------------------
# Projection drift diagnostics (T8)
# ---------------------------------------------------------------------------


class TestProjectionDriftDiagnostics:
    """Projection drift: on-disk vs rebuilt from Markdown."""

    def test_absent_projection_reported_as_info(self, tmp_path: Path) -> None:
        """No projection file → projection-absent (info, no action generated)."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        absent = [f for f in report.findings
                   if f.kind == "projection-absent"]
        assert len(absent) >= 1
        assert absent[0].severity == "info"
        # Absent projection does NOT generate an action (normal state).
        proj_actions = [a for a in report.proposed_actions
                         if a.kind == "rebuild-projection"]
        assert len(proj_actions) == 0

    def test_projection_current_when_matches_rebuilt(self, tmp_path: Path) -> None:
        """On-disk projection matches rebuilt → projection-current."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        # Write a valid projection that matches what would be rebuilt.
        _write_projection(repo)
        report = inspect_strategy_migration(repo)
        current = [f for f in report.findings
                    if f.kind == "projection-current"]
        assert len(current) >= 1
        assert current[0].severity == "info"

    def test_stale_projection_triggers_rebuild_action(self, tmp_path: Path) -> None:
        """On-disk projection differs from rebuilt → projection-drift + action."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        # Write a stale projection (different content).
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        proj_path.parent.mkdir(parents=True, exist_ok=True)
        proj_path.write_text('{"stale": true, "version": "old"}', encoding="utf-8")
        report = inspect_strategy_migration(repo)
        drift = [f for f in report.findings
                  if f.kind == "projection-drift"]
        assert len(drift) >= 1
        assert drift[0].severity == "warning"
        actions = [a for a in report.proposed_actions
                    if a.kind == "rebuild-projection"]
        assert len(actions) >= 1

    def test_unreadable_projection_reported(self, tmp_path: Path) -> None:
        """Invalid JSON projection → projection-stale + rebuild action."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        proj_path.parent.mkdir(parents=True, exist_ok=True)
        proj_path.write_text("not valid json!!!", encoding="utf-8")
        report = inspect_strategy_migration(repo)
        stale = [f for f in report.findings
                  if f.kind == "projection-stale"]
        assert len(stale) >= 1
        actions = [a for a in report.proposed_actions
                    if a.kind == "rebuild-projection"]
        assert len(actions) >= 1

    def test_malformed_strategy_skips_projection_check(self, tmp_path: Path) -> None:
        """Malformed strategy skips projection drift checks."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, "garbage\nnot valid\n---\n")
        report = inspect_strategy_migration(repo)
        # Should still be blocked for malformed, but no projection findings.
        proj_findings = [f for f in report.findings
                          if f.kind in ("projection-absent", "projection-current",
                                        "projection-drift", "projection-stale")]
        assert len(proj_findings) == 0

    def test_absent_strategy_skips_projection_check(self, tmp_path: Path) -> None:
        """Absent strategy skips projection drift checks."""
        repo = _make_repo(tmp_path)
        report = inspect_strategy_migration(repo)
        proj_findings = [f for f in report.findings
                          if f.kind in ("projection-absent", "projection-current",
                                        "projection-drift", "projection-stale")]
        assert len(proj_findings) == 0


# ---------------------------------------------------------------------------
# Store reconciliation diagnostics (T8)
# ---------------------------------------------------------------------------


class TestStoreReconciliationDiagnostics:
    """Store rows are cross-referenced against file artifacts (advisory)."""

    def test_store_orphan_link_reported(self, tmp_path: Path) -> None:
        """Store link referencing unknown ticket → orphan warning."""
        from unittest.mock import MagicMock

        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-a.md",
                       _minimal_ticket(_valid_ulid()))

        store = MagicMock()
        # Return a link where the ticket_id is not in the inventory.
        fake_link = MagicMock()
        fake_link.ticket_id = "01ARZ3NDEKTSV4RRFFQ69G5FXX"  # not in inventory
        fake_link.epic_id = "some-epic"
        store.list_ticket_epic_links.return_value = [fake_link]

        report = inspect_strategy_migration(repo, store=store)
        orphans = [f for f in report.findings
                    if f.kind == "store-orphan-link"]
        assert len(orphans) >= 1
        assert orphans[0].severity == "warning"

    def test_store_link_with_valid_refs_no_orphan(self, tmp_path: Path) -> None:
        """Store link referencing known ticket/epic → no orphan finding."""
        from unittest.mock import MagicMock

        repo = _make_repo(tmp_path)
        uid = _valid_ulid()
        content = _minimal_strategy_with_ticket_title(uid, "Ticket")
        _write_strategy(repo, content)
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{uid}-a.md", _minimal_ticket(uid))

        slug = "known-epic"
        _create_initiative_dir(repo, slug, title="Known Epic")

        store = MagicMock()
        fake_link = MagicMock()
        fake_link.ticket_id = uid
        fake_link.epic_id = slug
        store.list_ticket_epic_links.return_value = [fake_link]

        report = inspect_strategy_migration(repo, store=store)
        orphans = [f for f in report.findings
                    if f.kind == "store-orphan-link"]
        assert len(orphans) == 0

    def test_store_none_skips_reconciliation(self, tmp_path: Path) -> None:
        """Store=None skips reconciliation entirely."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{_valid_ulid()}-a.md",
                       _minimal_ticket(_valid_ulid()))
        report = inspect_strategy_migration(repo, store=None)
        store_orphans = [f for f in report.findings
                          if f.kind == "store-orphan-link"]
        assert len(store_orphans) == 0

    def test_store_has_store_relationship_summary(self, tmp_path: Path) -> None:
        """Store with links produces a store-relationship info finding."""
        from unittest.mock import MagicMock

        repo = _make_repo(tmp_path)
        uid = _valid_ulid()
        _write_strategy(repo, _minimal_strategy_with_ticket_title(uid, "T"))
        td = _make_tickets_dir(repo)
        _write_ticket(td, f"{uid}-a.md", _minimal_ticket(uid))

        slug = "my-epic"
        _create_initiative_dir(repo, slug, title="My Epic")

        store = MagicMock()
        fake_link = MagicMock()
        fake_link.ticket_id = uid
        fake_link.epic_id = slug
        store.list_ticket_epic_links.return_value = [fake_link]

        report = inspect_strategy_migration(repo, store=store)
        store_info = [f for f in report.findings
                       if f.kind == "store-relationship"]
        assert len(store_info) >= 1
        assert store_info[0].severity == "info"


# ---------------------------------------------------------------------------
# Boundary / edge cases
# ---------------------------------------------------------------------------


class TestBoundaryCases:
    """Edge cases for the migration inspector."""

    def test_repo_root_with_no_megaplan_dir(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        # No .megaplan at all
        report = inspect_strategy_migration(repo)
        assert report.status == "ok"
        assert report.version_status == "absent"
        assert report.tickets_dir_exists is False

    def test_non_ulid_ticket_not_roadmap_eligible(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        _write_ticket(td, "weird-name.md", _minimal_ticket("not-a-ulid"))
        report = inspect_strategy_migration(repo)
        assert report.status == "blocked"  # invalid ULID

    def test_multiple_findings_per_entry(self, tmp_path: Path) -> None:
        """A single file can generate multiple findings."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        td = _make_tickets_dir(repo)
        # Valid ULID but non-canonical filename → legacy-filename + roadmap-orphan
        uid = _valid_ulid()
        _write_ticket(td, "legacy-file.md", _minimal_ticket(uid))
        report = inspect_strategy_migration(repo)
        kinds = {f.kind for f in report.findings}
        assert FINDING_LEGACY_FILENAME in kinds
        assert FINDING_ROADMAP_ORPHAN in kinds

    def test_migration_report_str_fields(self, tmp_path: Path) -> None:
        """Ensure string fields are not empty when expected."""
        repo = _make_repo(tmp_path)
        _write_strategy(repo, _minimal_strategy())
        report = inspect_strategy_migration(repo)
        assert isinstance(report.current_version, str)
        assert len(report.current_version) > 0
        assert len(report.strategy_file_path) > 0
