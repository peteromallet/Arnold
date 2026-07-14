"""Compatibility E2E tests covering mixed-version and recovery behavior.

Exercises ``python -P -m arnold_pipelines.megaplan`` in temporary git
repositories for scenarios that span absent strategy, stale/deleted/mutated
projection files, unsupported strategy versions, legacy non-ULID ticket
artifacts, old projection formats, and fail-closed diagnostics for invalid
or non-canonical references.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.layout import strategy_file_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _megaplan_cmd(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -P -m arnold_pipelines.megaplan`` in *cwd*.

    Returns a ``CompletedProcess`` with captured stdout and stderr as text.

    The subprocess inherits a PYTHONPATH that places the local repository copy
    **before** any installed system/editable copies so that it always exercises
    the code under test.
    """
    _LOCAL_REPO = str(Path(__file__).resolve().parent.parent.parent.parent)
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _LOCAL_REPO + (os.pathsep + existing if existing else "")

    cmd = [sys.executable, "-P", "-m", "arnold_pipelines.megaplan", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _init_temp_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with ``.megaplan/`` scaffolding.

    Returns the repository root path.
    """
    repo = tmp_path / "compat_repo"
    repo.mkdir(parents=True)

    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "compat@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Compat Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# Compatibility Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create .megaplan/store directory (needed by FileStore for promotion).
    (repo / ".megaplan" / "store").mkdir(parents=True, exist_ok=True)

    return repo


def _parse_ulid(stdout: str) -> str:
    """Extract a ULID from stdout (last non-empty line)."""
    lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
    return lines[-1]


def _read_projection(repo: Path) -> dict:
    """Read the strategy projection JSON file."""
    proj_path = repo / ".megaplan" / "strategy.projection.json"
    return json.loads(proj_path.read_text(encoding="utf-8"))


def _read_strategy_md(repo: Path) -> str:
    """Read the authoritative STRATEGY.md content."""
    return strategy_file_path(repo).read_text(encoding="utf-8")


def _write_strategy_md(repo: Path, content: str) -> None:
    """Write (overwrite) the authoritative STRATEGY.md."""
    path = strategy_file_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _projection_exists(repo: Path) -> bool:
    """Check whether the projection JSON file exists."""
    return (repo / ".megaplan" / "strategy.projection.json").exists()


def _delete_projection(repo: Path) -> None:
    """Delete the projection JSON file if it exists."""
    proj_path = repo / ".megaplan" / "strategy.projection.json"
    if proj_path.exists():
        proj_path.unlink()


def _write_projection(repo: Path, content: str) -> None:
    """Write (overwrite) the projection JSON file."""
    (repo / ".megaplan" / "strategy.projection.json").write_text(
        content, encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Absent / missing strategy
# ---------------------------------------------------------------------------


class TestAbsentStrategy:
    """Commands that need a strategy file must fail gracefully when it is absent."""

    def test_strategy_show_fails_without_strategy(self, tmp_path: Path) -> None:
        """``strategy show`` fails when STRATEGY.md is absent."""
        repo = _init_temp_repo(tmp_path)
        # No strategy init — file is missing

        result = _megaplan_cmd("strategy", "show", "--json", cwd=repo)
        assert result.returncode != 0, (
            "strategy show should fail when STRATEGY.md is missing"
        )

    def test_strategy_list_fails_without_strategy(self, tmp_path: Path) -> None:
        """``strategy list`` fails when STRATEGY.md is absent."""
        repo = _init_temp_repo(tmp_path)

        result = _megaplan_cmd("strategy", "list", cwd=repo)
        assert result.returncode != 0, (
            "strategy list should fail when STRATEGY.md is missing"
        )

    def test_strategy_validate_fails_without_strategy(self, tmp_path: Path) -> None:
        """``strategy validate`` fails when STRATEGY.md is absent."""
        repo = _init_temp_repo(tmp_path)

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        assert result.returncode != 0, (
            "strategy validate should fail when STRATEGY.md is missing"
        )

    def test_strategy_project_fails_without_strategy(self, tmp_path: Path) -> None:
        """``strategy project`` fails when STRATEGY.md is absent."""
        repo = _init_temp_repo(tmp_path)

        result = _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        assert result.returncode != 0, (
            "strategy project should fail when STRATEGY.md is missing"
        )


# ---------------------------------------------------------------------------
# Stale or deleted projection
# ---------------------------------------------------------------------------


class TestStaleOrDeletedProjection:
    """The projection JSON is always rebuildable from Markdown.  When it is
    stale or missing, a fresh rebuild produces correct output."""

    def test_deleted_projection_rebuilt_from_markdown(
        self, tmp_path: Path
    ) -> None:
        """Delete projection → rebuild → file exists with correct content."""
        repo = _init_temp_repo(tmp_path)

        # Init strategy
        result = _megaplan_cmd("strategy", "init", cwd=repo)
        assert result.returncode == 0, f"strategy init failed: {result.stderr}"

        # Create first projection
        result = _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        assert result.returncode == 0
        assert _projection_exists(repo), "Projection should exist after --write"

        first_bytes = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        # Delete projection
        _delete_projection(repo)
        assert not _projection_exists(repo), "Projection should be deleted"

        # Rebuild from Markdown
        result = _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        assert result.returncode == 0, (
            f"Rebuild after delete failed: {result.stderr}"
        )
        assert _projection_exists(repo), "Projection should be re-created"

        second_bytes = (repo / ".megaplan" / "strategy.projection.json").read_bytes()
        assert first_bytes == second_bytes, (
            "Rebuilt projection should be byte-identical to original"
        )

    def test_stale_projection_overwritten_on_strategy_change(
        self, tmp_path: Path
    ) -> None:
        """When STRATEGY.md changes, re-projecting overwrites the stale
        projection with fresh content."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        # Create a ticket and add to roadmap via CLI
        result = _megaplan_cmd(
            "ticket", "new", "Stale Test Ticket", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0
        ticket_id = _parse_ulid(result.stdout)

        # Project
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        stale_bytes = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        # Direct Markdown edit: change the display title in strategy
        strategy_content = _read_strategy_md(repo)
        edited = strategy_content.replace(
            "Stale Test Ticket", "Updated Stale Title"
        )
        _write_strategy_md(repo, edited)

        # Re-project
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        fresh_bytes = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        # Fresh should differ from stale (title changed)
        assert stale_bytes != fresh_bytes, (
            "Projection should change after Markdown edit"
        )

        # Fresh projection should contain the updated title
        projection = _read_projection(repo)
        now_entries = projection["roadmap"]["Now"]
        assert any("Updated Stale Title" == e.get("title") for e in now_entries), (
            f"Fresh projection should contain updated title. Got: {now_entries}"
        )


# ---------------------------------------------------------------------------
# Unsupported strategy version
# ---------------------------------------------------------------------------


class TestUnsupportedStrategyVersion:
    """An unsupported ``schema_version`` in the frontmatter must produce
    diagnostics and the system must fail closed (no silent fallback)."""

    def test_unsupported_version_produces_parser_error(
        self, tmp_path: Path
    ) -> None:
        """A STRATEGY.md with an unsupported schema_version produces
        a hard diagnostic when validated."""
        repo = _init_temp_repo(tmp_path)

        # Write a strategy with an unsupported version
        content = """---
schema_version: megaplan-strategy-v999-unsupported
---

# Repository Strategy

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

## Next

## Later
"""
        _write_strategy_md(repo, content)

        # Validate — should fail
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        # With unsupported version, validation should provide diagnostics
        try:
            val_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            assert result.returncode != 0, (
                f"Validate with unsupported version should fail. "
                f"stdout: {result.stdout}"
            )
            return

        diags = val_data.get("diagnostics", [])
        if not diags:
            diags = val_data.get("details", {}).get("diagnostics", [])

        version_errors = [
            d for d in diags
            if d["severity"] in ("error", "warning")
            and ("version" in d["message"].lower()
                 or "schema" in d["message"].lower()
                 or "unsupported" in d["message"].lower())
        ]
        assert version_errors, (
            f"Should have diagnostics about unsupported version. Got: {diags}"
        )

    def test_unsupported_version_fail_closed_no_projection(
        self, tmp_path: Path
    ) -> None:
        """An unsupported schema_version must not silently produce a
        projection — the system must fail closed."""
        repo = _init_temp_repo(tmp_path)

        content = """---
schema_version: megaplan-strategy-v999-unsupported
---

# Repository Strategy

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

## Next

## Later
"""
        _write_strategy_md(repo, content)

        # Try to project
        result = _megaplan_cmd("strategy", "project", "--write", cwd=repo)

        # The system should either fail (non-zero exit) or if it succeeds,
        # the projection should carry diagnostic evidence of the issue.
        if result.returncode == 0:
            if _projection_exists(repo):
                projection = _read_projection(repo)
                val_summary = projection.get("validation_summary", {})
                # Even if projection was written, error_count must be > 0
                assert val_summary.get("error_count", 0) > 0, (
                    f"Projection with unsupported version must have errors. "
                    f"Got: {val_summary}"
                )
        # Non-zero exit is also acceptable (fail closed)


# ---------------------------------------------------------------------------
# Legacy non-ULID ticket files
# ---------------------------------------------------------------------------


class TestLegacyNonULIDTicketFiles:
    """Ticket artifacts with non-ULID (legacy) identifiers should either
    be accepted or produce clear diagnostics — never silently corrupt."""

    def test_non_ulid_ticket_ref_in_strategy_produces_error(
        self, tmp_path: Path
    ) -> None:
        """A non-ULID ticket ref in the strategy produces a hard diagnostic."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        # Inject a non-ULID ticket ref
        strategy_content = _read_strategy_md(repo)
        bad_line = "- [ticket:LEGACY-123] Legacy non-ULID ticket"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        # Validate — should produce errors
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        ticket_errors = [
            d for d in diags
            if d["severity"] == "error" and "LEGACY-123" in d["message"]
        ]
        assert ticket_errors, (
            f"Should have error about non-ULID ref 'LEGACY-123'. "
            f"Diagnostics: {diags}"
        )
        for te in ticket_errors:
            source = te.get("source")
            assert source is not None, (
                f"Non-ULID ref error must have source location: {te}"
            )
            assert "path" in source
            assert source["line"] > 0

    def test_mixed_valid_and_invalid_refs_in_strategy(
        self, tmp_path: Path
    ) -> None:
        """A strategy with a mix of valid ULID and legacy non-ULID refs
        surfaces only the invalid refs as errors."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        # Create a valid ticket
        result = _megaplan_cmd(
            "ticket", "new", "Valid Mixed Ticket", "-b", "Body",
            cwd=repo,
        )
        assert result.returncode == 0
        valid_id = _parse_ulid(result.stdout)

        # Add valid ticket to Now
        _megaplan_cmd(
            "strategy", "add",
            "ticket", valid_id,
            "--title", "Valid Mixed Ticket",
            "--horizon", "Now",
            cwd=repo,
        )

        # Also inject a non-ULID ref
        strategy_content = _read_strategy_md(repo)
        bad_line = "- [ticket:MIXED-LEGACY-REF] Mixed legacy ref"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        # Validate
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        legacy_errors = [
            d for d in diags
            if d["severity"] == "error" and "MIXED-LEGACY-REF" in d["message"]
        ]
        assert legacy_errors, (
            f"Should have error about legacy ref. Got: {diags}"
        )
        # The valid ULID should NOT have errors
        valid_errors = [
            d for d in diags
            if d["severity"] == "error" and valid_id in d["message"]
        ]
        assert not valid_errors, (
            f"Valid ULID {valid_id} should not produce errors. Got: {valid_errors}"
        )


# ---------------------------------------------------------------------------
# Old / mutated projection files
# ---------------------------------------------------------------------------


class TestOldProjectionFiles:
    """Old or hand-edited projection files are never used as authority.
    The system always rebuilds from Markdown."""

    def test_old_projection_format_overwritten_on_rebuild(
        self, tmp_path: Path
    ) -> None:
        """A projection with an old/deprecated schema version is overwritten
        when rebuilt from the authoritative Markdown."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        # Create a ticket and add to Now
        result = _megaplan_cmd(
            "ticket", "new", "Old Proj Test", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0

        # First, build a legitimate projection
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)

        # Now hand-edit the projection to look like an old format
        old_content = json.dumps(
            {
                "schema_version": "megaplan-strategy-projection-v0-old",
                "strategy_schema_version": "megaplan-strategy-v0",
                "stable_direction": [],
                "roadmap": {"Now": [], "Next": [], "Later": []},
                "validation_summary": {"error_count": 0, "warning_count": 0},
                "diagnostics": [],
            },
            indent=2,
        )
        _write_projection(repo, old_content)

        # Verify old projection is on disk
        old_bytes = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        # Rebuild from Markdown
        result = _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        assert result.returncode == 0, (
            f"Rebuild over old projection failed: {result.stderr}"
        )

        new_bytes = (repo / ".megaplan" / "strategy.projection.json").read_bytes()
        assert new_bytes != old_bytes, (
            "Rebuilt projection must overwrite the old/deprecated content"
        )

        # New projection should have current schema version
        projection = _read_projection(repo)
        assert projection.get("schema_version") != "megaplan-strategy-projection-v0-old", (
            "New projection must have current schema version, not the old one"
        )

    def test_mutated_projection_ignored_as_authority(
        self, tmp_path: Path
    ) -> None:
        """A hand-mutated projection file is ignored — the next rebuild
        from Markdown overwrites it with the correct content."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        # Create a ticket and add to Now
        result = _megaplan_cmd(
            "ticket", "new", "Mutated Proj Test", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0
        ticket_id = _parse_ulid(result.stdout)

        # Build legitimate projection first
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        legitimate_bytes = (
            repo / ".megaplan" / "strategy.projection.json"
        ).read_bytes()

        # Hand-mutate: inject a fake entry and change the title
        projection = _read_projection(repo)
        projection["roadmap"]["Now"].append(
            {
                "type": "ticket",
                "ref": "01FAKE00000000000000000000",
                "title": "Fake Injected Entry",
                "horizon": "Now",
                "source": {"path": ".megaplan/STRATEGY.md", "line": 99, "column": 1},
            }
        )
        # Also mutate an existing title
        for entry in projection["roadmap"]["Now"]:
            if entry["ref"] == ticket_id:
                entry["title"] = "MUTATED TITLE BY HAND"

        _write_projection(repo, json.dumps(projection, indent=2))

        # Rebuild from Markdown — must overwrite the mutated content
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        rebuilt_bytes = (
            repo / ".megaplan" / "strategy.projection.json"
        ).read_bytes()

        # The rebuilt content must match the legitimate original
        assert rebuilt_bytes == legitimate_bytes, (
            "Mutated projection must be overwritten; rebuild "
            "should produce byte-identical result to the original"
        )

        # Also verify: fake entry must NOT appear
        rebuilt = _read_projection(repo)
        fake_refs = [
            e["ref"] for entries in rebuilt["roadmap"].values()
            for e in entries if e["ref"] == "01FAKE00000000000000000000"
        ]
        assert not fake_refs, "Fake injected entry must not survive rebuild"

        # MUTATED title must not appear
        mutated_titles = [
            e.get("title") for entries in rebuilt["roadmap"].values()
            for e in entries if "MUTATED" in e.get("title", "")
        ]
        assert not mutated_titles, "Mutated title must not survive rebuild"


# ---------------------------------------------------------------------------
# Deterministic rebuild from Markdown
# ---------------------------------------------------------------------------


class TestDeterministicRebuildFromMarkdown:
    """Projection rebuild from Markdown is deterministic — same Markdown
    always produces byte-identical JSON."""

    def test_multiple_rebuilds_produce_identical_output(
        self, tmp_path: Path
    ) -> None:
        """Three rebuilds from the same Markdown produce identical bytes."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        # Create a ticket and add to Now
        result = _megaplan_cmd(
            "ticket", "new", "Deterministic Test", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0

        # Build1
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        bytes1 = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        # Delete and rebuild twice
        _delete_projection(repo)
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        bytes2 = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        _delete_projection(repo)
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        bytes3 = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        assert bytes1 == bytes2 == bytes3, (
            "All three rebuilds must produce byte-identical output"
        )

    def test_rebuild_after_promotion_produces_consistent_projection(
        self, tmp_path: Path
    ) -> None:
        """After promotion, rebuild from Markdown is deterministic."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        result = _megaplan_cmd(
            "ticket", "new", "Promo Rebuild Test", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        # Promote
        _megaplan_cmd("ticket", "promote", ticket_id, "--json", cwd=repo)

        # Build1
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        bytes1 = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        # Delete and rebuild
        _delete_projection(repo)
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        bytes2 = (repo / ".megaplan" / "strategy.projection.json").read_bytes()

        assert bytes1 == bytes2, (
            "Rebuild after promotion must be byte-identical"
        )


# ---------------------------------------------------------------------------
# Fail-closed diagnostics for invalid ticket refs
# ---------------------------------------------------------------------------


class TestFailClosedInvalidTicketRefs:
    """Invalid (non-ULID) ticket refs produce fail-closed diagnostics with
    actionable source locations."""

    def test_completely_malformed_ticket_ref_with_special_chars(
        self, tmp_path: Path
    ) -> None:
        """Ticket ref with special characters produces source-located error."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        strategy_content = _read_strategy_md(repo)
        bad_line = "- [ticket:!!!BAD-REF!!!] Completely malformed"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        bad_ref_errors = [
            d for d in diags
            if d["severity"] == "error" and "!!!BAD-REF!!!" in d["message"]
        ]
        assert bad_ref_errors, (
            f"Should have error about malformed ref. Got: {diags}"
        )
        for be in bad_ref_errors:
            assert be.get("source") is not None
            assert "path" in be["source"]
            assert "line" in be["source"]

    def test_empty_ticket_ref_produces_error(self, tmp_path: Path) -> None:
        """An empty ticket ref (`[ticket:]`) produces an error."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        strategy_content = _read_strategy_md(repo)
        bad_line = "- [ticket:] Empty ref ticket"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        empty_ref_errors = [
            d for d in diags
            if d["severity"] == "error"
            and ("empty" in d["message"].lower() or "ref" in d["message"].lower())
        ]
        assert empty_ref_errors, (
            f"Should have error about empty ref. Got: {diags}"
        )

    def test_near_ulid_but_too_short_produces_error(
        self, tmp_path: Path
    ) -> None:
        """A ref that looks like a ULID but is too short produces an error."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        strategy_content = _read_strategy_md(repo)
        # 25 chars instead of 26
        bad_line = "- [ticket:01KTH21DTP1HR3ER5W7SRRJVV] Too short ULID"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        # Should have an error about invalid ticket ref format
        assert any(d["severity"] == "error" for d in diags), (
            f"Should have errors for invalid ticket ref. Got: {diags}"
        )


# ---------------------------------------------------------------------------
# Fail-closed diagnostics for non-canonical epic refs
# ---------------------------------------------------------------------------


class TestFailClosedNonCanonicalEpicRefs:
    """Non-canonical epic refs (uppercase, special chars) produce
    fail-closed diagnostics with actionable source locations."""

    def test_uppercase_epic_ref_produces_error(self, tmp_path: Path) -> None:
        """Uppercase characters in an epic slug produce an error."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        strategy_content = _read_strategy_md(repo)
        bad_line = "- [epic:UPPERCASE-SLUG] Uppercase epic"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        epic_errors = [
            d for d in diags
            if d["severity"] == "error" and "UPPERCASE-SLUG" in d["message"]
        ]
        assert epic_errors, (
            f"Should have error about non-canonical uppercase epic. Got: {diags}"
        )
        for ee in epic_errors:
            assert ee.get("source") is not None
            assert "path" in ee["source"]
            assert "line" in ee["source"]

    def test_epic_ref_with_spaces_produces_error(self, tmp_path: Path) -> None:
        """An epic ref containing spaces produces an error."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        strategy_content = _read_strategy_md(repo)
        bad_line = "- [epic:slug with spaces] Epic with spaces"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        epic_errors = [
            d for d in diags
            if d["severity"] == "error" and "slug with spaces" in d["message"]
        ]
        assert epic_errors, (
            f"Should have error about epic with spaces. Got: {diags}"
        )

    def test_epic_ref_starting_with_non_alpha_produces_error(
        self, tmp_path: Path
    ) -> None:
        """An epic ref starting with a non-alpha character produces an error."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        strategy_content = _read_strategy_md(repo)
        bad_line = "- [epic:123-starts-with-digit] Digit-starting epic"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{bad_line}\n",
        )
        _write_strategy_md(repo, edited)

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        epic_errors = [
            d for d in diags
            if d["severity"] == "error"
            and "123-starts-with-digit" in d["message"]
        ]
        assert epic_errors, (
            f"Should have error about digit-starting epic. Got: {diags}"
        )

    def test_valid_canonical_epic_slug_produces_no_error(
        self, tmp_path: Path
    ) -> None:
        """A valid canonical epic slug produces no errors (positive control)."""
        repo = _init_temp_repo(tmp_path)
        _megaplan_cmd("strategy", "init", cwd=repo)

        # Create a ticket and promote to get a valid epic slug
        result = _megaplan_cmd(
            "ticket", "new", "Canonical Slug Test", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)
        promote_result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json", cwd=repo
        )
        epic_id = json.loads(promote_result.stdout)["epic_id"]

        # Validate — the promoted epic slug should produce no format errors
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("diagnostics", [])
        if not diags:
            diags = val_data.get("details", {}).get("diagnostics", []) or []

        epic_format_errors = [
            d for d in diags
            if d["severity"] == "error" and epic_id in d["message"]
        ]
        assert not epic_format_errors, (
            f"Canonical epic slug '{epic_id}' should not produce format errors. "
            f"Got: {epic_format_errors}"
        )
