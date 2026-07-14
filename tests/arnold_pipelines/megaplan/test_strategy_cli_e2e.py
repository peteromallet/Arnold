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
import yaml


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


def _find_ticket_file(repo: Path, ticket_id: str) -> Path | None:
    """Find the ``.md`` file for *ticket_id* in ``.megaplan/tickets/``."""
    tickets_dir = repo / ".megaplan" / "tickets"
    if not tickets_dir.is_dir():
        return None
    for entry in tickets_dir.iterdir():
        if entry.suffix == ".md" and entry.name.startswith(f"{ticket_id}-"):
            return entry
    return None


def _read_ticket_frontmatter(repo: Path, ticket_id: str) -> dict:
    """Read the YAML frontmatter from a ticket ``.md`` file."""
    ticket_path = _find_ticket_file(repo, ticket_id)
    if ticket_path is None:
        return {}
    text = ticket_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = yaml.safe_load(parts[1])
    return fm if isinstance(fm, dict) else {}


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

    # ------------------------------------------------------------------
    # Direct Markdown edit & CLI edit tests (T3 extensions)
    # ------------------------------------------------------------------

    def test_direct_markdown_horizon_edit_reflected_by_cli(
        self, tmp_path: Path
    ) -> None:
        """Direct Markdown edit of STRATEGY.md horizon is reflected by CLI tools.

        After adding a ticket to ``Next`` via CLI, directly edit the
        Markdown to move the reference to ``Now``.  Then verify that
        ``strategy show``, ``strategy list``, ``strategy validate``, and
        ``strategy project --write`` all pick up the change — proving
        that the Markdown is the single authority.
        """
        repo = _init_temp_repo(tmp_path)

        # ---- 1. Initialize strategy and create ticket ------------------
        result = _megaplan_cmd("strategy", "init", cwd=repo)
        assert result.returncode == 0, f"strategy init failed: {result.stderr}"

        result = _megaplan_cmd(
            "ticket", "new", "Markdown Edit Ticket", "-b", "Body",
            cwd=repo,
        )
        assert result.returncode == 0
        ticket_id = _parse_ulid(result.stdout)

        # ---- 2. Add ticket to Next via CLI -----------------------------
        result = _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "Markdown Edit Ticket",
            "--horizon", "Next",
            cwd=repo,
        )
        assert result.returncode == 0, f"strategy add failed: {result.stderr}"

        # Sanity: ticket is in Next, not Now
        strategy_content = _read_strategy_md(repo)
        assert ticket_id in strategy_content
        now_section = strategy_content.split("## Now\n")[1].split("\n## ")[0]
        next_section = strategy_content.split("## Next\n")[1].split("\n## ")[0]
        assert f"[ticket:{ticket_id}]" not in now_section, (
            "Ticket should NOT be in Now before Markdown edit"
        )
        assert f"[ticket:{ticket_id}]" in next_section, (
            "Ticket should be in Next before Markdown edit"
        )

        # ---- 3. Direct Markdown edit: move ticket from Next to Now -----
        line_to_move = f"- [ticket:{ticket_id}] Markdown Edit Ticket"
        assert line_to_move in strategy_content, (
            f"Expected '{line_to_move}' in strategy content"
        )

        # Remove the ticket line from Next and insert it under Now.
        edited = strategy_content.replace(
            f"## Next\n\n{line_to_move}\n",
            "## Next\n\n",
        )
        edited = edited.replace(
            "## Now\n\n",
            f"## Now\n\n{line_to_move}\n",
        )
        (repo / ".megaplan" / "STRATEGY.md").write_text(edited, encoding="utf-8")

        # ---- 4. Verify CLI tools reflect the Markdown edit -------------

        # 4a. strategy show --json
        result = _megaplan_cmd("strategy", "show", "--json", cwd=repo)
        assert result.returncode == 0
        show_data = json.loads(result.stdout)
        strategy_proj = show_data.get("strategy", {})
        now_entries = strategy_proj.get("roadmap", {}).get("Now", [])
        next_entries = strategy_proj.get("roadmap", {}).get("Next", [])

        assert any(e["ref"] == ticket_id for e in now_entries), (
            f"strategy show should reflect Markdown edit: ticket {ticket_id} "
            f"should be in Now. Now entries: {now_entries}"
        )
        assert not any(e["ref"] == ticket_id for e in next_entries), (
            f"strategy show should reflect Markdown edit: ticket {ticket_id} "
            f"should NOT be in Next. Next entries: {next_entries}"
        )

        # 4b. strategy list
        result = _megaplan_cmd("strategy", "list", cwd=repo)
        assert result.returncode == 0
        assert ticket_id in result.stdout, (
            f"strategy list should include {ticket_id}"
        )

        # 4c. strategy validate — should pass (no hard errors from valid
        #     Markdown edits)
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        assert result.returncode == 0, (
            f"strategy validate should succeed after valid Markdown edit: "
            f"{result.stderr}"
        )
        val_data = json.loads(result.stdout)
        assert val_data.get("clean") is True, (
            f"Validation should report clean=True. Got: {val_data}"
        )
        assert val_data.get("error_count") == 0, (
            f"Validation should have 0 errors. Got: {val_data}"
        )

        # 4d. strategy project --write — rebuild and verify
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        if proj_path.exists():
            proj_path.unlink()

        result = _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        assert result.returncode == 0, (
            f"strategy project --write failed: {result.stderr}"
        )
        projection = _read_projection(repo)
        proj_now = projection["roadmap"]["Now"]
        assert any(e["ref"] == ticket_id and e["type"] == "ticket" for e in proj_now), (
            f"Projection should have ticket {ticket_id} in Now. Got: {proj_now}"
        )

    def test_cli_remove_and_readd_as_edit_operation(
        self, tmp_path: Path
    ) -> None:
        """Using ``strategy remove`` + ``strategy add`` as a CLI edit pattern.

        Add a ticket to ``Next``, then remove it and re-add to ``Now``
        with a different title — effectively editing the roadmap entry
        entirely through CLI operations.
        """
        repo = _init_temp_repo(tmp_path)

        # ---- 1. Setup --------------------------------------------------
        _megaplan_cmd("strategy", "init", cwd=repo)

        result = _megaplan_cmd(
            "ticket", "new", "CLI Edit Ticket", "-b", "Body",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        # ---- 2. Add to Next ---------------------------------------------
        _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "CLI Edit Ticket",
            "--horizon", "Next",
            cwd=repo,
        )

        # ---- 3. Remove it -----------------------------------------------
        result = _megaplan_cmd(
            "strategy", "remove",
            "ticket", ticket_id,
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"strategy remove failed: {result.stderr}\\n{result.stdout}"
        )

        # Verify it's gone
        strategy_content = _read_strategy_md(repo)
        assert ticket_id not in strategy_content, (
            "Ticket should be removed from strategy after remove"
        )

        # ---- 4. Re-add to Now with new title ----------------------------
        _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "CLI Edit Ticket (Edited)",
            "--horizon", "Now",
            cwd=repo,
        )

        # ---- 5. Verify the edit took effect -----------------------------
        strategy_content = _read_strategy_md(repo)
        assert ticket_id in strategy_content, (
            "Ticket should be back in strategy after re-add"
        )
        assert f"[ticket:{ticket_id}] CLI Edit Ticket (Edited)" in strategy_content, (
            f"Strategy should contain edited title. Got:\n{strategy_content}"
        )

        # Verify it's in Now, not Next
        result = _megaplan_cmd("strategy", "show", "--json", cwd=repo)
        show_data = json.loads(result.stdout)
        strategy_proj = show_data.get("strategy", {})
        now_entries = strategy_proj.get("roadmap", {}).get("Now", [])
        next_entries = strategy_proj.get("roadmap", {}).get("Next", [])

        assert any(e["ref"] == ticket_id for e in now_entries), (
            f"Ticket should be in Now after re-add. Now: {now_entries}"
        )
        assert not any(e["ref"] == ticket_id for e in next_entries), (
            f"Ticket should NOT be in Next after re-add. Next: {next_entries}"
        )

        # Projection should also reflect the edit
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        projection = _read_projection(repo)
        proj_now = projection["roadmap"]["Now"]
        edited_entry = next(
            (e for e in proj_now if e["ref"] == ticket_id), None
        )
        assert edited_entry is not None, (
            f"Projection should have edited entry in Now. Got: {proj_now}"
        )
        assert edited_entry["title"] == "CLI Edit Ticket (Edited)", (
            f"Projection title should match edited title. "
            f"Got: {edited_entry['title']}"
        )

    def test_direct_markdown_edit_before_promotion_lifecycle(
        self, tmp_path: Path
    ) -> None:
        """Direct Markdown edit before promotion: full lifecycle with
        Markdown as the authority for horizon placement, then promote
        via CLI and verify the retained ticket ULID and distinct epic slug.
        """
        repo = _init_temp_repo(tmp_path)

        # ---- 1. Initialize strategy & create ticket (outside roadmap) ---
        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Markdown Lifecycle Ticket", "-b", "Body",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        # ---- 2. Add to Next via CLI -------------------------------------
        _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "Markdown Lifecycle Ticket",
            "--horizon", "Next",
            cwd=repo,
        )

        # ---- 3. Direct Markdown edit: move from Next to Now -------------
        strategy_content = _read_strategy_md(repo)
        line_to_move = (
            f"- [ticket:{ticket_id}] Markdown Lifecycle Ticket"
        )
        edited = strategy_content.replace(
            f"## Next\n\n{line_to_move}\n",
            "## Next\n\n",
        )
        edited = edited.replace(
            "## Now\n\n",
            f"## Now\n\n{line_to_move}\n",
        )
        (repo / ".megaplan" / "STRATEGY.md").write_text(edited, encoding="utf-8")

        # Sanity: ticket is now under Now
        strategy_content = _read_strategy_md(repo)
        now_section = strategy_content.split("## Now\n")[1].split("\n## ")[0]
        assert f"[ticket:{ticket_id}]" in now_section, (
            "After Markdown edit, ticket should be under ## Now"
        )

        # ---- 4. Promote ticket to epic (should update strategy) ---------
        result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"ticket promote failed: {result.stderr}\\n{result.stdout}"
        )
        promote_output = json.loads(result.stdout)
        assert promote_output["ticket_id"] == ticket_id, (
            "Promoted ticket_id should match the original ULID"
        )
        assert promote_output["strategy_updated"] is True, (
            "Promotion should update strategy when ticket is on the roadmap"
        )
        epic_id = promote_output["epic_id"]
        assert epic_id and epic_id != ticket_id, (
            f"Epic slug '{epic_id}' must differ from ticket ULID '{ticket_id}'"
        )

        # ---- 5. Verify replacement of roadmap entry with distinct epic --
        strategy_content = _read_strategy_md(repo)
        # Ticket ULID should be gone from strategy
        assert ticket_id not in strategy_content, (
            "Ticket ULID should be removed from strategy after promotion"
        )
        # Epic slug should be present
        assert f"[epic:{epic_id}]" in strategy_content, (
            f"Epic reference [epic:{epic_id}] should appear in strategy"
        )
        # Epic should be under Now
        now_section = strategy_content.split("## Now\n")[1].split("\n## ")[0]
        assert f"[epic:{epic_id}]" in now_section, (
            "Epic should appear under ## Now after promotion"
        )

        # ---- 6. Projection rebuild and validation -----------------------
        # Delete any existing projection
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        if proj_path.exists():
            proj_path.unlink()

        result = _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        assert result.returncode == 0
        projection = _read_projection(repo)

        now_entries = projection["roadmap"]["Now"]
        # Ticket should be replaced by epic in the projection
        assert not any(e["ref"] == ticket_id for e in now_entries), (
            f"Ticket {ticket_id} should NOT appear in projection Now "
            f"after promotion"
        )
        epic_entry = next(
            (e for e in now_entries if e["ref"] == epic_id), None
        )
        assert epic_entry is not None, (
            f"Epic {epic_id} should appear in projection Now"
        )
        assert epic_entry["type"] == "epic", (
            f"Epic entry should have type 'epic', got {epic_entry['type']}"
        )

        # ---- 7. Projection reproducibility -------------------------------
        first_bytes = proj_path.read_bytes()
        proj_path.unlink()
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        second_bytes = proj_path.read_bytes()
        assert first_bytes == second_bytes, (
            "Re-projection from Markdown should produce byte-identical output"
        )

    def test_strategy_remove_entry_verified_by_cli(
        self, tmp_path: Path
    ) -> None:
        """``strategy remove`` removes an entry and CLI tools confirm it's gone."""
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Remove Test Ticket", "-b", "Body",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        # Add to Next
        _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "Remove Test Ticket",
            "--horizon", "Next",
            cwd=repo,
        )

        # Remove it
        result = _megaplan_cmd(
            "strategy", "remove",
            "ticket", ticket_id,
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"strategy remove should succeed: {result.stderr}"
        )

        # Verify not in strategy content
        strategy_content = _read_strategy_md(repo)
        assert ticket_id not in strategy_content, (
            "Ticket should be removed from STRATEGY.md"
        )

        # Verify not in strategy show
        result = _megaplan_cmd("strategy", "show", "--json", cwd=repo)
        show_data = json.loads(result.stdout)
        strategy_proj = show_data.get("strategy", {})
        all_entries = []
        for horizon_entries in strategy_proj.get("roadmap", {}).values():
            all_entries.extend(horizon_entries)
        assert not any(e["ref"] == ticket_id for e in all_entries), (
            f"strategy show should not include removed ticket {ticket_id}"
        )

        # Removing a non-existent entry should fail
        result = _megaplan_cmd(
            "strategy", "remove",
            "ticket", ticket_id,
            cwd=repo,
        )
        assert result.returncode != 0, (
            "Removing a non-existent entry should fail"
        )

    def test_cli_move_entry_between_horizons(
        self, tmp_path: Path
    ) -> None:
        """``strategy move`` moves an entry between horizons and CLI
        tools reflect the new location, including after projection rebuild.
        """
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Move Test Ticket", "-b", "Body",
            cwd=repo,
        )
        ticket_id = _parse_ulid(result.stdout)

        # Add to Later
        _megaplan_cmd(
            "strategy", "add",
            "ticket", ticket_id,
            "--title", "Move Test Ticket",
            "--horizon", "Later",
            cwd=repo,
        )

        # Move to Now
        result = _megaplan_cmd(
            "strategy", "move",
            "ticket", ticket_id,
            "--to", "Now",
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"strategy move failed: {result.stderr}"
        )

        # Verify in Now, not Later
        strategy_content = _read_strategy_md(repo)
        now_section = strategy_content.split("## Now\n")[1].split("\n## ")[0]
        later_section = strategy_content.split("## Later\n")[1].split("\n## ")[0] if "## Later\n" in strategy_content else ""
        assert f"[ticket:{ticket_id}]" in now_section, (
            "Ticket should be under ## Now after move"
        )
        assert f"[ticket:{ticket_id}]" not in later_section, (
            "Ticket should NOT be under ## Later after move"
        )

        # Verify projection after rebuild
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        if proj_path.exists():
            proj_path.unlink()
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        projection = _read_projection(repo)
        assert any(e["ref"] == ticket_id for e in projection["roadmap"]["Now"]), (
            "Projection should have ticket in Now after move"
        )
        assert not any(e["ref"] == ticket_id for e in projection["roadmap"]["Later"]), (
            "Projection should NOT have ticket in Later after move"
        )

    # ------------------------------------------------------------------
    # T4: Promotion provenance, relationship evidence, lifecycle
    #     isolation, and actionable diagnostics
    # ------------------------------------------------------------------

    def test_promotion_provenance_in_ticket_artifact(
        self, tmp_path: Path
    ) -> None:
        """After promotion, the ticket artifact carries ``promoted_to_epic``
        provenance with kind, resolves_on_complete, and provenance string.
        """
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Provenance Test Ticket", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0
        ticket_id = _parse_ulid(result.stdout)

        # Promote to epic
        result = _megaplan_cmd(
            "ticket", "promote", ticket_id, "--json",
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"ticket promote failed: {result.stderr}\\n{result.stdout}"
        )
        promote_output = json.loads(result.stdout)
        epic_id = promote_output["epic_id"]
        assert epic_id and epic_id != ticket_id

        # Read the ticket file frontmatter to assert provenance evidence
        fm = _read_ticket_frontmatter(repo, ticket_id)
        assert fm, (
            f"Should be able to read ticket {ticket_id} frontmatter"
        )

        epics = fm.get("epics", [])
        assert epics, (
            "Ticket should have 'epics' relationship entries after promotion"
        )

        promoted_link = next(
            (e for e in epics if e.get("kind") == "promoted_to_epic"), None
        )
        assert promoted_link is not None, (
            f"Ticket should have a 'promoted_to_epic' link. Got epics: {epics}"
        )

        # Relationship evidence: kind, epic_id, resolves_on_complete, provenance
        assert promoted_link.get("epic_id") == epic_id, (
            f"Link should reference epic '{epic_id}', "
            f"got '{promoted_link.get('epic_id')}'"
        )
        assert promoted_link.get("resolves_on_complete") is True, (
            "Default promotion should set resolves_on_complete=True"
        )
        provenance = promoted_link.get("provenance", "")
        assert isinstance(provenance, str) and provenance, (
            f"Provenance should be a non-empty string, got: {provenance!r}"
        )
        assert ticket_id in provenance, (
            f"Provenance '{provenance}' should contain ticket_id '{ticket_id}'"
        )

        # Ticket and epic identities are distinct
        assert ticket_id != epic_id, (
            "Ticket ULID and epic slug must be distinct identities"
        )

    def test_addressed_ticket_evidence_stays_in_artifact_not_strategy(
        self, tmp_path: Path
    ) -> None:
        """Completion/addressing evidence stays in the ticket artifact;
        the strategy and projection carry only identity keys.
        """
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Isolation Test Ticket", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0
        ticket_id = _parse_ulid(result.stdout)

        # Mark the ticket as addressed via CLI
        result = _megaplan_cmd(
            "ticket", "addressed", ticket_id,
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"ticket addressed failed: {result.stderr}"
        )

        # ---- The ticket artifact carries the status --------------------------
        fm = _read_ticket_frontmatter(repo, ticket_id)
        assert fm.get("status") == "addressed", (
            f"Ticket artifact should have status 'addressed', "
            f"got: {fm.get('status')}"
        )

        # ---- The strategy Markdown does NOT contain completion evidence ------
        strategy_content = _read_strategy_md(repo)
        # Find the ticket line
        ticket_line = None
        for line in strategy_content.splitlines():
            if ticket_id in line and "[ticket:" in line:
                ticket_line = line
                break
        assert ticket_line is not None, (
            "Ticket should still be referenced in strategy"
        )
        # The Markdown entry line `- [ticket:ULID] Display Title` must only
        # carry identity + display title.  Lifecycle markers like
        # `status: addressed` must not appear in the strategy.
        for forbidden in ("status:", "resolution_note:", "addressed_at:",
                          "completed_at:", "lifecycle:"):
            assert forbidden not in ticket_line.lower(), (
                f"Strategy line must not contain '{forbidden}': {ticket_line}"
            )

        # ---- Projection entries carry only canonical identity keys -----------
        proj_path = repo / ".megaplan" / "strategy.projection.json"
        if proj_path.exists():
            proj_path.unlink()
        _megaplan_cmd("strategy", "project", "--write", cwd=repo)
        projection = _read_projection(repo)
        now_entries = projection["roadmap"]["Now"]
        ticket_entry = next(
            (e for e in now_entries if e["ref"] == ticket_id), None
        )
        assert ticket_entry is not None, (
            "Ticket should appear in projection Now"
        )

        canonical_keys = {"type", "ref", "title", "horizon", "source"}
        actual_keys = set(ticket_entry.keys())
        assert actual_keys == canonical_keys, (
            f"Projection entry must have exactly {canonical_keys}, "
            f"got: {actual_keys}"
        )
        for forbidden in ("status", "body", "resolution", "addressed",
                          "completed", "lifecycle"):
            assert forbidden not in ticket_entry, (
                f"Projection entry must not contain '{forbidden}'"
            )

        # ---- Validation emits a source-located warning (not error) -----------
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        # Warnings-only means return code 0
        val_data = json.loads(result.stdout)
        diags = val_data.get("diagnostics", [])
        addressed_warnings = [
            d for d in diags
            if d["severity"] == "warning" and "addressed" in d["message"].lower()
        ]
        assert addressed_warnings, (
            f"Should have a warning about addressed ticket. "
            f"Diagnostics: {diags}"
        )
        for dw in addressed_warnings:
            assert dw.get("source") is not None, (
                f"Addressed-ticket warning must have source location: {dw}"
            )
            assert "path" in dw["source"], (
                f"Source must have 'path': {dw['source']}"
            )
            assert dw["source"]["line"] > 0, (
                f"Source line must be positive: {dw['source']}"
            )

    def test_malformed_ticket_ref_produces_source_located_diagnostic(
        self, tmp_path: Path
    ) -> None:
        """Non-ULID ticket refs in strategy produce actionable, source-located
        diagnostics via ``strategy validate --json``.
        """
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)

        # Inject a malformed ticket ref directly into the Markdown
        strategy_content = _read_strategy_md(repo)
        malformed_line = "- [ticket:NOT-A-VALID-ULID] Malformed ticket ref"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{malformed_line}\n",
        )
        (repo / ".megaplan" / "STRATEGY.md").write_text(edited, encoding="utf-8")

        # Validate — should produce errors (non-zero exit)
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        # On errors the output is an error_response JSON with details
        val_data = json.loads(result.stdout)

        # error_response wraps diagnostics in details
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            # Regular success path (unlikely here but handle gracefully)
            diags = val_data.get("diagnostics", [])

        malformed_errors = [
            d for d in diags
            if d["severity"] == "error" and "NOT-A-VALID-ULID" in d["message"]
        ]
        assert malformed_errors, (
            f"Should have error about 'NOT-A-VALID-ULID'. "
            f"Diagnostics: {diags}"
        )
        for me in malformed_errors:
            source = me.get("source")
            assert source is not None, (
                f"Malformed-ref error must have source location: {me}"
            )
            assert "path" in source, (
                f"Source must have 'path': {source}"
            )
            assert "line" in source and source["line"] > 0, (
                f"Source line must be positive: {source}"
            )
            # The message must identify the malformed ref
            assert "NOT-A-VALID-ULID" in me["message"], (
                f"Diagnostic message must quote the malformed ref: {me['message']}"
            )

    def test_stale_display_title_produces_source_located_warning(
        self, tmp_path: Path
    ) -> None:
        """When a ticket title changes but the strategy display title is stale,
        ``strategy validate --json`` emits a source-located warning.
        """
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)
        result = _megaplan_cmd(
            "ticket", "new", "Original Title", "-b", "Body",
            "--roadmap-horizon", "Now",
            cwd=repo,
        )
        assert result.returncode == 0
        ticket_id = _parse_ulid(result.stdout)

        # Change the ticket title via CLI edit
        result = _megaplan_cmd(
            "ticket", "edit", ticket_id, "--title", "Updated Title",
            cwd=repo,
        )
        assert result.returncode == 0, (
            f"ticket edit failed: {result.stderr}"
        )

        # Strategy still contains the old title
        strategy_content = _read_strategy_md(repo)
        assert "Original Title" in strategy_content, (
            "Strategy should still have the old display title"
        )
        assert "Updated Title" not in strategy_content, (
            "Strategy should NOT contain the updated ticket title (stale)"
        )

        # Validate — should produce a stale-title warning
        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("diagnostics", [])

        stale_warnings = [
            d for d in diags
            if (d["severity"] == "warning"
                and "stale" in d["message"].lower()
                and ticket_id in d["message"])
        ]
        assert stale_warnings, (
            f"Should have stale-title warning for ticket '{ticket_id}'. "
            f"Diagnostics: {diags}"
        )
        for sw in stale_warnings:
            source = sw.get("source")
            assert source is not None, (
                f"Stale-title warning must have source location: {sw}"
            )
            assert "path" in source, (
                f"Source must have 'path': {source}"
            )
            assert source["line"] > 0, (
                f"Source line must be positive: {source}"
            )
            # Message identifies the stale title
            assert "Original Title" in sw["message"], (
                f"Warning should mention the stale title 'Original Title': "
                f"{sw['message']}"
            )

    def test_non_canonical_epic_ref_produces_source_located_diagnostic(
        self, tmp_path: Path
    ) -> None:
        """Non-canonical epic refs (uppercase, special chars) produce
        source-located diagnostic errors.
        """
        repo = _init_temp_repo(tmp_path)

        _megaplan_cmd("strategy", "init", cwd=repo)

        # Inject a non-canonical epic ref
        strategy_content = _read_strategy_md(repo)
        malformed_line = "- [epic:Not-A-Canonical-Slug] Malformed epic ref"
        edited = strategy_content.replace(
            "## Now\n\n",
            f"## Now\n\n{malformed_line}\n",
        )
        (repo / ".megaplan" / "STRATEGY.md").write_text(edited, encoding="utf-8")

        result = _megaplan_cmd("strategy", "validate", "--json", cwd=repo)
        val_data = json.loads(result.stdout)
        diags = val_data.get("details", {}).get("diagnostics", [])
        if not diags:
            diags = val_data.get("diagnostics", [])

        epic_errors = [
            d for d in diags
            if d["severity"] == "error"
            and "Not-A-Canonical-Slug" in d["message"]
        ]
        assert epic_errors, (
            f"Should have error about non-canonical epic ref. "
            f"Diagnostics: {diags}"
        )
        for ee in epic_errors:
            source = ee.get("source")
            assert source is not None, (
                f"Non-canonical epic ref error must have source location: {ee}"
            )
            assert "path" in source, (
                f"Source must have 'path': {source}"
            )
            assert source["line"] > 0, (
                f"Source line must be positive: {source}"
            )
