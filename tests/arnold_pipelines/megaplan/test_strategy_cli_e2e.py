"""Subprocess E2E coverage for the full ticket→strategy→promotion→projection flow.

Exercises the entire lifecycle using ``python -P -m arnold_pipelines.megaplan``
in a temporary git repository:

1. Create a ticket **outside** the roadmap (no ``--roadmap-horizon``).
2. Add it to the ``Next`` horizon via ``strategy add``.
3. Move it to the ``Now`` horizon via ``strategy move``.
4. Promote it to a new epic via ``ticket promote --json``.
5. Rebuild the projection JSON via ``strategy project --write``.
6. Validate final Markdown references and projection reproducibility.

The test asserts projection reproducibility from the authoritative Markdown
source — the projection is regenerated on demand and never treated as an
authority itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _megaplan_cmd(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -P -m arnold_pipelines.megaplan`` in *cwd* with the given args.

    Returns a ``CompletedProcess`` with captured stdout and stderr as text.

    The subprocess inherits a PYTHONPATH that places the local repository copy
    **before** any installed system/editable copies so that it always exercises
    the code under test, not a stale installed version.
    """
    # Prepend the local checkout so the subprocess picks up the code under test
    # rather than the editable install at /workspace/arnold.
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
    repo = tmp_path / "e2e_repo"
    repo.mkdir(parents=True)

    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "e2e@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "E2E Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# E2E Test Repo\n")
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
    return (repo / ".megaplan" / "STRATEGY.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# E2E flow
# ---------------------------------------------------------------------------

class TestStrategyCliE2E:
    """End-to-end subprocess tests covering the full ticket→strategy→promotion→projection flow."""

    def test_full_ticket_to_strategy_to_promotion_to_projection_flow(
        self, tmp_path: Path
    ) -> None:
        """Full E2E flow: create ticket → add to Next → move to Now → promote → project → validate."""
        repo = _init_temp_repo(tmp_path)

        # ---- 1. Initialize strategy -----------------------------------------
        result = _megaplan_cmd("strategy", "init", cwd=repo)
        assert result.returncode == 0, f"strategy init failed: {result.stderr}"
        assert (repo / ".megaplan" / "STRATEGY.md").exists(), (
            "STRATEGY.md should exist after init"
        )

        # ---- 2. Create a ticket outside the roadmap (no --roadmap-horizon) --
        result = _megaplan_cmd(
            "ticket", "new", "E2E Integration Ticket", "-b", "Body for E2E test",
            cwd=repo,
        )
        assert result.returncode == 0, f"ticket new failed: {result.stderr}"
        ticket_id = _parse_ulid(result.stdout)
        assert ticket_id, "Should get a ULID from ticket new"
        assert len(ticket_id) == 26, f"Expected 26-char ULID, got: {ticket_id!r}"

        # Validate: ticket ID should NOT appear in the strategy yet
        strategy_content = _read_strategy_md(repo)
        assert ticket_id not in strategy_content, (
            "Ticket ULID should not be in strategy before explicit add"
        )

        # ---- 3. Add ticket to Next horizon ----------------------------------
        result = _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "E2E Integration Ticket",
            "--horizon", "Next",
            cwd=repo,
        )
        assert result.returncode == 0, f"strategy add failed: {result.stderr}\n{result.stdout}"

        strategy_content = _read_strategy_md(repo)
        assert ticket_id in strategy_content, (
            "Ticket ULID should appear in strategy after add to Next"
        )
        assert f"[ticket:{ticket_id}]" in strategy_content, (
            "Strategy should contain the ticket reference in [ticket:ULID] format"
        )

        # ---- 4. Move ticket from Next to Now ---------------------------------
        result = _megaplan_cmd(
            "strategy", "move",
            "ticket", ticket_id,
            "--to", "Now",
            cwd=repo,
        )
        assert result.returncode == 0, f"strategy move failed: {result.stderr}\n{result.stdout}"

        strategy_content = _read_strategy_md(repo)
        assert ticket_id in strategy_content, (
            "Ticket ULID should still be in strategy after move"
        )
        # The ticket should be under ## Now, not ## Next
        now_section = strategy_content.split("## Now\n")[1].split("\n## ")[0]
        assert f"[ticket:{ticket_id}]" in now_section, (
            "Ticket should appear under ## Now after move"
        )

        # ---- 5. Promote ticket to epic --------------------------------------
        result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"ticket promote failed: {result.stderr}\n{result.stdout}"
        )

        promote_output = json.loads(result.stdout)
        assert promote_output["ticket_id"] == ticket_id
        assert promote_output["strategy_updated"] is True, (
            "Promotion should update the strategy when ticket is on the roadmap"
        )
        epic_id = promote_output["epic_id"]
        assert epic_id, "Promotion should return an epic_id"
        assert epic_id != ticket_id, (
            "Epic ID (slug) must differ from ticket ULID"
        )

        # ---- 6. Rebuild projection JSON -------------------------------------
        result = _megaplan_cmd(
            "strategy", "project", "--write",
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"strategy project --write failed: {result.stderr}\n{result.stdout}"
        )
        assert (repo / ".megaplan" / "strategy.projection.json").exists(), (
            "strategy.projection.json should exist after project --write"
        )

        # ---- 7. Validate final references -----------------------------------

        # 7a. Validate projection JSON content
        projection = _read_projection(repo)
        assert "roadmap" in projection, "Projection should contain roadmap"
        roadmap = projection["roadmap"]

        # The ticket should NOT appear in the roadmap (replaced by epic)
        now_entries = roadmap.get("Now", [])
        ticket_refs_in_now = [e["ref"] for e in now_entries if e["ref"] == ticket_id]
        assert not ticket_refs_in_now, (
            f"Ticket {ticket_id} should NOT appear in Now after promotion; "
            f"it should be replaced by the epic. Got entries: {now_entries}"
        )

        # The epic should appear in Now
        epic_refs_in_now = [e["ref"] for e in now_entries if e["ref"] == epic_id]
        assert epic_refs_in_now, (
            f"Epic {epic_id} should appear in Now after promotion. "
            f"Now entries: {now_entries}"
        )

        # The epic entry should have type "epic"
        epic_entry = next(e for e in now_entries if e["ref"] == epic_id)
        assert epic_entry["type"] == "epic", (
            f"Epic entry should have type 'epic', got {epic_entry['type']}"
        )

        # Next and Later should be empty (no entries there)
        assert roadmap.get("Next", []) == [], (
            "Next should be empty after move + promote"
        )
        assert roadmap.get("Later", []) == [], (
            "Later should be empty"
        )

        # 7b. Validate authoritative STRATEGY.md
        strategy_content = _read_strategy_md(repo)
        # Ticket ULID should NOT appear in strategy anymore (replaced by epic)
        assert ticket_id not in strategy_content, (
            "Ticket ULID should be removed from strategy after promotion"
        )
        # Epic slug should appear in strategy
        assert f"[epic:{epic_id}]" in strategy_content, (
            f"Epic reference [epic:{epic_id}] should appear in strategy"
        )
        # Epic should be under ## Now (re-read strategy after promotion)
        now_section_after = strategy_content.split("## Now\n")[1].split("\n## ")[0]
        assert f"[epic:{epic_id}]" in now_section_after, (
            "Epic should appear under ## Now after promotion"
        )

        # 7c. Validate projection reproducibility: re-project and compare
        # ``strategy project`` (no flags) prints the projection JSON to stdout
        # followed by the StepResponse dict.  Delete the on-disk projection,
        # re-project with --write, and compare the bytes.
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        first_bytes = proj_path.read_bytes()
        proj_path.unlink()
        assert not proj_path.exists()

        result2 = _megaplan_cmd(
            "strategy", "project", "--write",
            cwd=repo,
        )
        assert result2.returncode == 0, (
            f"strategy project --write failed: {result2.stderr}"
        )
        assert proj_path.exists(), "Projection file should be re-created"
        second_bytes = proj_path.read_bytes()

        # Both projections should be byte-identical (deterministic output)
        assert first_bytes == second_bytes, (
            "Re-projection from Markdown should produce byte-identical output"
        )

        # 7d. Verify the projection contains the expected structure and
        # the validation summary is present (diagnostics from template
        # entries with missing artifacts are expected and acceptable).
        val_summary = projection.get("validation_summary", {})
        assert "error_count" in val_summary, (
            "Validation summary should include error_count"
        )
        assert "warning_count" in val_summary, (
            "Validation summary should include warning_count"
        )
        # The projection schema and stable direction are present
        assert "schema_version" in projection
        assert "stable_direction" in projection

    def test_promotion_idempotency_via_cli(self, tmp_path: Path) -> None:
        """Promoting the same ticket twice via CLI should succeed (idempotent)."""
        repo = _init_temp_repo(tmp_path)

        # Init strategy
        result = _megaplan_cmd("strategy", "init", cwd=repo)
        assert result.returncode == 0

        # Create ticket with roadmap opt-in
        result = _megaplan_cmd(
            "ticket", "new", "Idempotent Ticket", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0
        ticket_id = _parse_ulid(result.stdout)

        # First promotion
        result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        assert result.returncode == 0
        first = json.loads(result.stdout)
        assert first["strategy_updated"] is True

        # Second promotion (idempotent)
        result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        assert result.returncode == 0
        second = json.loads(result.stdout)
        # The second promotion should succeed (idempotent) — strategy may or
        # may not be marked as updated depending on whether the epic was
        # already in the roadmap after the first promotion.
        assert second["ticket_id"] == ticket_id
        assert second["epic_id"] == first["epic_id"]

    def test_cli_strategy_show_reflects_promotion(self, tmp_path: Path) -> None:
        """``strategy show`` should reflect the promoted epic after the full flow."""
        repo = _init_temp_repo(tmp_path)

        # Init + create ticket + add to Next + move to Now + promote
        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Show Test Ticket", "-b", "Body",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "Show Test Ticket", "--horizon", "Next",
            cwd=repo,
        )
        _megaplan_cmd(
            "strategy", "move",
            "ticket", ticket_id,
            "--to", "Now",
            cwd=repo,
        )
        promote_result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        epic_id = json.loads(promote_result.stdout)["epic_id"]

        # strategy show --json
        result = _megaplan_cmd("strategy", "show", "--json", cwd=repo)
        assert result.returncode == 0
        show_data = json.loads(result.stdout)

        # The --json response nests the projection under the "strategy" key
        strategy_proj = show_data.get("strategy", {})
        now_entries = strategy_proj.get("roadmap", {}).get("Now", [])
        assert any(e["ref"] == epic_id and e["type"] == "epic" for e in now_entries), (
            f"strategy show should contain the epic {epic_id} in Now. "
            f"Got: {now_entries}"
        )
        assert not any(e["ref"] == ticket_id for e in now_entries), (
            f"strategy show should NOT contain the ticket {ticket_id} after promotion"
        )

    def test_cli_strategy_list_reflects_promotion(self, tmp_path: Path) -> None:
        """``strategy list`` should show the epic after promotion."""
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "List Test Ticket", "-b", "Body",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "List Test Ticket", "--horizon", "Next",
            cwd=repo,
        )
        _megaplan_cmd(
            "strategy", "move",
            "ticket", ticket_id,
            "--to", "Now",
            cwd=repo,
        )
        promote_result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        epic_id = json.loads(promote_result.stdout)["epic_id"]

        # strategy list (stdout)
        result = _megaplan_cmd("strategy", "list", cwd=repo)
        assert result.returncode == 0
        assert epic_id in result.stdout, (
            f"strategy list should include epic {epic_id}. Got: {result.stdout}"
        )
        assert ticket_id not in result.stdout, (
            f"strategy list should NOT include ticket {ticket_id} after promotion"
        )

    def test_projection_reproducibility_from_markdown(
        self, tmp_path: Path
    ) -> None:
        """Projection JSON should be reproducible from the authoritative Markdown alone.

        Even if the ``strategy.projection.json`` file is deleted, re-running
        ``strategy project --write`` should produce an identical file.
        """
        repo = _init_temp_repo(tmp_path)

        # Setup: init + create ticket with roadmap opt-in + promote
        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Repro Test", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)
        _megaplan_cmd("ticket", "promote", ticket_id, "--json", cwd=repo)

        # First projection
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        first_bytes = proj_path.read_bytes()

        # Delete the projection
        proj_path.unlink()
        assert not proj_path.exists()

        # Re-project — should produce identical content from Markdown alone
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        second_bytes = proj_path.read_bytes()

        assert first_bytes == second_bytes, (
            "Re-projection from Markdown should produce byte-identical output"
        )

    def test_non_roadmap_ticket_promotion_does_not_force_strategy_entry(
        self, tmp_path: Path
    ) -> None:
        """A ticket created outside the roadmap should not be forced into strategy on promotion."""
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)

        # Create ticket without --roadmap-horizon
        result = _megaplan_cmd(
            "ticket", "new", "Non-Strategic Ticket", "-b", "Body",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        # Promote without skip-strategy (should not force entry)
        result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        promote_output = json.loads(result.stdout)
        assert promote_output["strategy_updated"] is False, (
            "Non-roadmap ticket promotion should not update strategy"
        )

        # Verify strategy content has neither ticket nor epic
        strategy_content = _read_strategy_md(repo)
        assert ticket_id not in strategy_content, (
            "Non-roadmap ticket should not appear in strategy after promotion"
        )
        epic_id = promote_output["epic_id"]
        assert f"[epic:{epic_id}]" not in strategy_content, (
            "Non-roadmap epic should not be forced into strategy after promotion"
        )

    def test_ticket_roadmap_horizon_opt_in_preflight(
        self, tmp_path: Path
    ) -> None:
        """``ticket new --roadmap-horizon`` should fail before ticket creation if strategy is missing."""
        repo = _init_temp_repo(tmp_path)
        # No strategy init — strategy file missing

        result = _megaplan_cmd(
            "ticket", "new", "Preflight Test", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode != 0, (
            "ticket new --roadmap-horizon should fail when strategy is missing"
        )
        assert "strategy file not found" in result.stderr.lower(), (
            f"Error should mention missing strategy. Got: {result.stderr}"
        )
