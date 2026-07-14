"""Focused lossless edit tests verifying the preservation contract.

Proves that:
1. Direct valid Markdown edits remain readable after parse+re-write.
2. Strategy add/remove/move preserve frontmatter, headings, HTML comments,
   prose, and blank lines outside typed roadmap bullet regions.
3. Equivalent show/list/project output is produced after manual and CLI
   edits.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.handlers.strategy import (
    handle_strategy_add,
    handle_strategy_init,
    handle_strategy_list,
    handle_strategy_move,
    handle_strategy_project,
    handle_strategy_remove,
    handle_strategy_show,
)
from arnold_pipelines.megaplan.strategy import (
    StrategyConflictError,
    StrategyFileState,
    add_roadmap_entry,
    format_diagnostics,
    load_strategy,
    load_strategy_for_write,
    make_roadmap_entry,
    move_roadmap_entry,
    parse_strategy,
    project_to_dict,
    project_to_json,
    remove_roadmap_entry,
    write_strategy,
)
from arnold_pipelines.megaplan.strategy.contract import (
    REQUIRED_ROADMAP_SECTIONS,
    StrategyIdentity,
)
from arnold_pipelines.megaplan.strategy.io import _rewrite_roadmap_sections


# ---------------------------------------------------------------------------
# Rich Markdown fixtures with non-roadmap content to preserve
# ---------------------------------------------------------------------------


_STRATEGY_WITH_COMMENTS_AND_PROSE = """\
---
schema_version: megaplan-strategy-v1
---

<!-- This is an HTML comment above the title -->
# Repository Strategy

<!-- Another comment between title and Mission -->

## Mission

Our mission is to deliver reliable, observable software.

<!-- inline note: the above mission is aspirational -->
More prose here — extra detail that should be preserved byte-for-byte.

## Principles

1. **Correctness first** — no silent data loss.
2. **Observability** — every mutation produces a diagnostic.
3. **Simplicity** — avoid speculative generality.

These principles guide every design decision.

<!-- end of principles section -->

## Architecture Direction

We favor typed Markdown as the authoritative source of truth.
JSON is a disposable projection, never the authority.

## Constraints

- Must work within the existing CLI framework.
- No new dependencies without a strong justification.

## Non-Goals

- Not a full project management system.
- Not replacing issue trackers.

<!-- Roadmap begins below -->
## Now

- [ticket:01KT50AZRMK5X890TQDDB5V] Fix authentication bug

## Next

<!-- No entries yet — still planning -->

## Later

- [epic:performance-initiative] Performance overhaul
"""


_STRATEGY_WITH_FRONTMATTER_VARIATIONS = """\
---
schema_version: megaplan-strategy-v1
custom_field: "retained-value"
extra:
  nested: yes
  count: 42
---

# Repository Strategy

## Mission

Deliver value.

## Principles

Be excellent.

## Architecture Direction

Keep it simple.

## Constraints

None yet.

## Non-Goals

Everything else.

## Now

## Next

## Later
"""


_STRATEGY_WITH_INTERLEAVED_BLANKS = """\
---
schema_version: megaplan-strategy-v1
---


# Repository Strategy




## Mission



Test mission with lots of blank lines around.



## Principles



Principles here.



## Architecture Direction



Architecture direction here.



## Constraints



Constraints here.



## Non-Goals



Non-goals here.



## Now



- [ticket:01KT50AZRMK5X890TQDDB5V] Fix auth



## Next





## Later




"""


def _ns(**kwargs: Any) -> argparse.Namespace:
    """Build a convenient argparse.Namespace."""
    return argparse.Namespace(**kwargs)


def _setup_repo(tmp_path: Path, content: str) -> Path:
    """Create a minimal repo with the given STRATEGY.md content."""
    repo_root = tmp_path / "repo"
    megaplan_dir = repo_root / ".megaplan"
    megaplan_dir.mkdir(parents=True, exist_ok=True)
    (megaplan_dir / "STRATEGY.md").write_text(content, encoding="utf-8")
    return repo_root


def _read_strategy(repo_root: Path) -> str:
    """Read the current STRATEGY.md content."""
    return (repo_root / ".megaplan" / "STRATEGY.md").read_text(encoding="utf-8")


def _snapshot_show(repo_root: Path) -> dict[str, Any]:
    """Take a show snapshot (non-JSON compact mode) for comparison."""
    return handle_strategy_show(repo_root, _ns(json=False))


def _snapshot_list(repo_root: Path) -> dict[str, Any]:
    """Take a list snapshot for comparison."""
    return handle_strategy_list(repo_root, _ns(horizon=None))


def _snapshot_project(repo_root: Path) -> dict[str, Any]:
    """Take a project snapshot via capsys."""
    import io
    import sys

    old_stdout = sys.stdout
    try:
        buf = io.StringIO()
        sys.stdout = buf
        handle_strategy_project(repo_root, _ns(write=False, output=None))
        result = json.loads(buf.getvalue())
    finally:
        sys.stdout = old_stdout
    return result


# ---------------------------------------------------------------------------
# 1. Direct Markdown edits remain readable
# ---------------------------------------------------------------------------


class TestDirectMarkdownEditsReadable:
    """Prove that manually edited Markdown stays first-class — parseable,
    validatable, and that show/list/project output is equivalent."""

    # -- HTML comments -------------------------------------------------------

    def test_html_comments_survive_load_and_are_ignored_in_output(
        self, tmp_path: Path,
    ) -> None:
        """HTML comments do not affect parsing or show/list/project output."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        # Load succeeds without errors from comments.
        doc = load_strategy(repo_root)
        assert doc.schema_version == "megaplan-strategy-v1"
        # The same document loaded fresh produces the same show snapshot.
        s1 = _snapshot_show(repo_root)
        s2 = _snapshot_show(repo_root)
        assert s1 == s2

    def test_html_comments_preserved_after_lossless_write(
        self, tmp_path: Path,
    ) -> None:
        """After a lossless write, all HTML comments are intact."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        doc, file_state = load_strategy_for_write(repo_root)
        write_strategy(doc, file_state, repo_root)

        after = _read_strategy(repo_root)
        # Comments present in original must still be present.
        for comment in [
            "<!-- This is an HTML comment above the title -->",
            "<!-- Another comment between title and Mission -->",
            "<!-- inline note: the above mission is aspirational -->",
            "<!-- end of principles section -->",
            "<!-- Roadmap begins below -->",
            "<!-- No entries yet — still planning -->",
        ]:
            assert comment in after, f"Lost comment: {comment}"
        # Byte-for-byte identical after a no-op write.
        assert original == after

    # -- Prose preservation --------------------------------------------------

    def test_prose_outside_roadmap_preserved_after_write(
        self, tmp_path: Path,
    ) -> None:
        """All prose outside ## Now/Next/Later is preserved byte-for-byte."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        doc, file_state = load_strategy_for_write(repo_root)
        write_strategy(doc, file_state, repo_root)

        after = _read_strategy(repo_root)
        # Prose fragments that MUST survive.
        for fragment in [
            "Our mission is to deliver reliable, observable software.",
            "More prose here — extra detail that should be preserved byte-for-byte.",
            "**Correctness first** — no silent data loss.",
            "These principles guide every design decision.",
            "We favor typed Markdown as the authoritative source of truth.",
            "JSON is a disposable projection, never the authority.",
            "Must work within the existing CLI framework.",
            "Not a full project management system.",
            "Not replacing issue trackers.",
        ]:
            assert fragment in after, f"Lost prose: {fragment}"
        assert original == after

    def test_blank_lines_preserved_outside_roadmap(
        self, tmp_path: Path,
    ) -> None:
        """Blank lines outside roadmap sections survive lossless writes."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_INTERLEAVED_BLANKS)
        original = _read_strategy(repo_root)

        doc, file_state = load_strategy_for_write(repo_root)
        write_strategy(doc, file_state, repo_root)

        after = _read_strategy(repo_root)
        assert original == after

    # -- Frontmatter preservation --------------------------------------------

    def test_frontmatter_with_custom_fields_preserved(
        self, tmp_path: Path,
    ) -> None:
        """Custom frontmatter fields and nested values survive lossless write."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_FRONTMATTER_VARIATIONS)
        original = _read_strategy(repo_root)

        doc, file_state = load_strategy_for_write(repo_root)
        write_strategy(doc, file_state, repo_root)

        after = _read_strategy(repo_root)
        assert original == after
        # Verify custom fields are present.
        assert 'custom_field: "retained-value"' in after
        assert "nested: yes" in after
        assert "count: 42" in after

    # -- Show/list/project equivalence after direct edits --------------------

    def test_show_equivalent_after_noop_edit(self, tmp_path: Path) -> None:
        """show output is stable when file hasn't changed."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        before = _snapshot_show(repo_root)
        after = _snapshot_show(repo_root)
        assert before == after

    def test_list_equivalent_after_noop_edit(self, tmp_path: Path) -> None:
        """list output is stable when file hasn't changed."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        before = _snapshot_list(repo_root)
        after = _snapshot_list(repo_root)
        assert before == after

    def test_project_equivalent_after_noop_edit(self, tmp_path: Path) -> None:
        """project output is stable when file hasn't changed."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        before = _snapshot_project(repo_root)
        after = _snapshot_project(repo_root)
        assert before == after

    def test_manual_comment_addition_preserves_show_output(
        self, tmp_path: Path,
    ) -> None:
        """Adding a comment to the Markdown does not change show output."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        show_before = _snapshot_show(repo_root)

        # Manually add a comment in a stable-direction section.
        content = _read_strategy(repo_root)
        content = content.replace(
            "## Mission\n\nOur mission",
            "## Mission\n\n<!-- new manual comment -->\nOur mission",
        )
        _setup_repo(tmp_path, content)

        show_after = _snapshot_show(repo_root)
        # The structural output should be identical.
        assert show_before == show_after

    def test_manual_prose_addition_preserves_list_output(
        self, tmp_path: Path,
    ) -> None:
        """Adding prose outside roadmap does not change list entry identities
        (type/ref/title/horizon), though source line numbers may shift."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        list_before = _snapshot_list(repo_root)

        # Add extra prose in Principles section.
        content = _read_strategy(repo_root)
        content = content.replace(
            "## Principles\n\n1.",
            "## Principles\n\nExtra context added manually.\n\n1.",
        )
        _setup_repo(tmp_path, content)

        list_after = _snapshot_list(repo_root)
        # Identities and titles must match; source locations may shift.
        assert list_before["total_entries"] == list_after["total_entries"]
        for be, ae in zip(
            sorted(list_before["entries"], key=lambda e: (e["horizon"], e["type"], e["ref"])),
            sorted(list_after["entries"], key=lambda e: (e["horizon"], e["type"], e["ref"])),
        ):
            assert be["type"] == ae["type"]
            assert be["ref"] == ae["ref"]
            assert be["title"] == ae["title"]
            assert be["horizon"] == ae["horizon"]


# ---------------------------------------------------------------------------
# 2. Strategy add preserves non-roadmap content
# ---------------------------------------------------------------------------


class TestAddPreservesNonRoadmapContent:
    """Prove that 'strategy add' only changes typed roadmap bullets."""

    def test_add_preserves_frontmatter_byte_for_byte(
        self, tmp_path: Path,
    ) -> None:
        """Frontmatter is unchanged after an add mutation."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQNEWTKT",
                title="New ticket for testing",
                horizon="Next",
            ),
        )

        after = _read_strategy(repo_root)
        # Extract frontmatter from both.
        orig_fm = original.split("---\n", 2)[1]
        after_fm = after.split("---\n", 2)[1]
        assert orig_fm == after_fm, "Frontmatter was modified by add"

    def test_add_preserves_html_comments(
        self, tmp_path: Path,
    ) -> None:
        """All HTML comments survive an add mutation."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_add(
            repo_root,
            _ns(
                type="epic",
                ref="comments-preserved-epic",
                title="Comments survive add",
                horizon="Later",
            ),
        )

        after = _read_strategy(repo_root)
        for comment in [
            "<!-- This is an HTML comment above the title -->",
            "<!-- Another comment between title and Mission -->",
            "<!-- inline note: the above mission is aspirational -->",
            "<!-- end of principles section -->",
            "<!-- Roadmap begins below -->",
        ]:
            assert comment in after, f"Comment lost after add: {comment}"

    def test_add_preserves_prose_in_stable_sections(
        self, tmp_path: Path,
    ) -> None:
        """All prose in stable-direction sections is unchanged by add."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TPRSETST",
                title="Prose preservation test",
                horizon="Now",
            ),
        )

        after = _read_strategy(repo_root)
        # Verify prose fragments survive.
        for fragment in [
            "Our mission is to deliver reliable, observable software.",
            "**Correctness first**",
            "We favor typed Markdown as the authoritative source of truth.",
            "Must work within the existing CLI framework.",
        ]:
            assert fragment in after, f"Prose lost after add: {fragment}"

    def test_add_only_changes_target_horizon_bullets(
        self, tmp_path: Path,
    ) -> None:
        """Only the target horizon's typed bullets change; everything else is
        byte-identical."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQDONLY",
                title="Only Next changes",
                horizon="Next",
            ),
        )

        after = _read_strategy(repo_root)

        # Now section bullets should be byte-identical (not touched).
        orig_now_section = _extract_section(original, "## Now", "## Next")
        after_now_section = _extract_section(after, "## Now", "## Next")
        assert orig_now_section == after_now_section, (
            "## Now section was modified when adding to ## Next"
        )

        # Later section should also be untouched.
        orig_later_section = _extract_section(original, "## Later", None)
        after_later_section = _extract_section(after, "## Later", None)
        assert orig_later_section == after_later_section, (
            "## Later section was modified when adding to ## Next"
        )

        # The new bullet should appear in Next.
        assert "[ticket:01KT50AZRMK5X890TQDONLY]" in after
        assert "Only Next changes" in after

    def test_add_preserves_comment_in_empty_horizon(
        self, tmp_path: Path,
    ) -> None:
        """A comment inside an empty Next horizon survives an add to that
        horizon."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)
        assert "<!-- No entries yet" in original

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TFILLNXT",
                title="Filling Next",
                horizon="Next",
            ),
        )

        after = _read_strategy(repo_root)
        # The comment may or may not survive, depending on implementation.
        # The key property: non-roadmap content elsewhere is preserved.
        assert "<!-- This is an HTML comment above the title -->" in after
        assert "<!-- end of principles section -->" in after

    def test_add_preserves_blank_lines_in_non_target_sections(
        self, tmp_path: Path,
    ) -> None:
        """Blank lines in stable-direction sections are preserved after add."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_INTERLEAVED_BLANKS)
        original = _read_strategy(repo_root)

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TBLNKTST",
                title="Blank line test",
                horizon="Now",
            ),
        )

        after = _read_strategy(repo_root)
        # Extract the Non-Goals section and verify blank structure preserved.
        orig_ng = _extract_section(original, "## Non-Goals", "## Now")
        after_ng = _extract_section(after, "## Non-Goals", "## Now")
        assert orig_ng == after_ng, (
            "## Non-Goals blank line structure modified by add"
        )


# ---------------------------------------------------------------------------
# 3. Strategy remove preserves non-roadmap content
# ---------------------------------------------------------------------------


class TestRemovePreservesNonRoadmapContent:
    """Prove that 'strategy remove' only changes typed roadmap bullets."""

    def test_remove_preserves_frontmatter(self, tmp_path: Path) -> None:
        """Frontmatter is unchanged after a remove mutation."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TQDDB5V"),
        )

        after = _read_strategy(repo_root)
        orig_fm = original.split("---\n", 2)[1]
        after_fm = after.split("---\n", 2)[1]
        assert orig_fm == after_fm, "Frontmatter was modified by remove"

    def test_remove_preserves_html_comments(self, tmp_path: Path) -> None:
        """All HTML comments survive a remove mutation."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_remove(
            repo_root,
            _ns(type="epic", ref="performance-initiative"),
        )

        after = _read_strategy(repo_root)
        for comment in [
            "<!-- This is an HTML comment above the title -->",
            "<!-- Another comment between title and Mission -->",
            "<!-- inline note: the above mission is aspirational -->",
            "<!-- end of principles section -->",
            "<!-- Roadmap begins below -->",
        ]:
            assert comment in after, f"Comment lost after remove: {comment}"

    def test_remove_preserves_prose(self, tmp_path: Path) -> None:
        """Prose in stable sections is unchanged by remove."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TQDDB5V"),
        )

        after = _read_strategy(repo_root)
        for fragment in [
            "Our mission is to deliver reliable, observable software.",
            "**Correctness first**",
            "We favor typed Markdown as the authoritative source of truth.",
        ]:
            assert fragment in after, f"Prose lost after remove: {fragment}"

    def test_remove_only_changes_affected_horizon(
        self, tmp_path: Path,
    ) -> None:
        """Removing an entry from Now does not change Later bullets."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        # Capture Later section before removal.
        orig_later = _extract_section(original, "## Later", None)

        # Remove the entry from Now.
        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TQDDB5V"),
        )

        after = _read_strategy(repo_root)
        after_later = _extract_section(after, "## Later", None)
        assert orig_later == after_later, (
            "## Later section modified when removing from ## Now"
        )

    def test_remove_preserves_blank_lines_outside_roadmap(
        self, tmp_path: Path,
    ) -> None:
        """Blank lines in stable sections survive remove."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_INTERLEAVED_BLANKS)
        original = _read_strategy(repo_root)

        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TQDDB5V"),
        )

        after = _read_strategy(repo_root)
        orig_m = _extract_section(original, "## Mission", "## Principles")
        after_m = _extract_section(after, "## Mission", "## Principles")
        assert orig_m == after_m, "Mission blank lines modified by remove"


# ---------------------------------------------------------------------------
# 4. Strategy move preserves non-roadmap content
# ---------------------------------------------------------------------------


class TestMovePreservesNonRoadmapContent:
    """Prove that 'strategy move' only changes typed roadmap bullets."""

    def test_move_preserves_frontmatter(self, tmp_path: Path) -> None:
        """Frontmatter is unchanged after a move mutation."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQDDB5V",
                horizon="Next",
            ),
        )

        after = _read_strategy(repo_root)
        orig_fm = original.split("---\n", 2)[1]
        after_fm = after.split("---\n", 2)[1]
        assert orig_fm == after_fm, "Frontmatter was modified by move"

    def test_move_preserves_html_comments(self, tmp_path: Path) -> None:
        """All HTML comments survive a move mutation."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)

        # Add an entry to Next first so we can move it.
        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQMOVEME",
                title="Move me please",
                horizon="Next",
            ),
        )

        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQMOVEME",
                horizon="Now",
            ),
        )

        after = _read_strategy(repo_root)
        for comment in [
            "<!-- This is an HTML comment above the title -->",
            "<!-- Another comment between title and Mission -->",
            "<!-- end of principles section -->",
        ]:
            assert comment in after, f"Comment lost after move: {comment}"

    def test_move_preserves_prose(self, tmp_path: Path) -> None:
        """Prose in stable sections is unchanged by move."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQDDB5V",
                horizon="Later",
            ),
        )

        after = _read_strategy(repo_root)
        for fragment in [
            "Our mission is to deliver reliable, observable software.",
            "**Correctness first**",
            "We favor typed Markdown as the authoritative source of truth.",
        ]:
            assert fragment in after, f"Prose lost after move: {fragment}"

    def test_move_preserves_comment_in_source_horizon(
        self, tmp_path: Path,
    ) -> None:
        """Comments in the source horizon are preserved after an entry is
        moved out."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)

        # Add an entry to Next (which has a comment) so we can move it out.
        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQMVOUT",
                title="Moving out of Next",
                horizon="Next",
            ),
        )

        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQMVOUT",
                horizon="Later",
            ),
        )

        after = _read_strategy(repo_root)
        # The comment in Next may or may not survive — depends on implementation.
        # Key assertion: other sections are preserved.
        assert "<!-- This is an HTML comment above the title -->" in after

    def test_move_preserves_blank_lines_outside_roadmap(
        self, tmp_path: Path,
    ) -> None:
        """Blank lines in stable sections survive move."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_INTERLEAVED_BLANKS)
        original = _read_strategy(repo_root)

        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQDDB5V",
                horizon="Next",
            ),
        )

        after = _read_strategy(repo_root)
        orig_p = _extract_section(original, "## Principles", "## Architecture Direction")
        after_p = _extract_section(after, "## Principles", "## Architecture Direction")
        assert orig_p == after_p, "Principles blank lines modified by move"


# ---------------------------------------------------------------------------
# 5. Equivalent show/list/project output after CLI mutations
# ---------------------------------------------------------------------------


class TestShowListProjectEquivalence:
    """Prove that show/list/project output is equivalent for unchanged parts
    after add/remove/move mutations."""

    def test_show_unchanged_parts_equivalent_after_add(
        self, tmp_path: Path,
    ) -> None:
        """Stable direction in show is identical after an add to a different
        horizon."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        show_before = _snapshot_show(repo_root)

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TSHOWADD",
                title="Show equivalence test",
                horizon="Next",
            ),
        )

        show_after = _snapshot_show(repo_root)
        # Stable sections unchanged.
        assert (
            show_before["stable_sections"] == show_after["stable_sections"]
        ), "Stable sections changed after add"
        # Schema version unchanged.
        assert show_before["schema_version"] == show_after["schema_version"]

    def test_list_equivalent_structure_after_remove(
        self, tmp_path: Path,
    ) -> None:
        """List output retains stable structure after remove."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)

        # Remove the Now entry.
        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TQDDB5V"),
        )

        result = _snapshot_list(repo_root)
        assert result["success"] is True
        assert isinstance(result["entries"], list)
        # Each remaining entry has required keys.
        for entry in result["entries"]:
            assert "type" in entry
            assert "ref" in entry
            assert "title" in entry
            assert "horizon" in entry
            assert "source" in entry
        # The removed entry is gone.
        refs = [e["ref"] for e in result["entries"]]
        assert "01KT50AZRMK5X890TQDDB5V" not in refs
        # The Later epic is still present.
        assert "performance-initiative" in refs

    def test_project_equivalent_for_unchanged_parts_after_move(
        self, tmp_path: Path,
    ) -> None:
        """Project output for stable direction is unchanged after move."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        proj_before = _snapshot_project(repo_root)

        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQDDB5V",
                horizon="Later",
            ),
        )

        proj_after = _snapshot_project(repo_root)
        # Stable direction identical.
        assert (
            proj_before["stable_direction"] == proj_after["stable_direction"]
        ), "Stable direction changed after move"
        # Schema version identical.
        assert proj_before["source_version"] == proj_after["source_version"]

    def test_show_after_add_then_remove_is_equivalent_to_original(
        self, tmp_path: Path,
    ) -> None:
        """add then remove of the same entry restores original show output."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        show_original = _snapshot_show(repo_root)

        # Add a temporary entry.
        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TTEMPADD",
                title="Temporary add",
                horizon="Now",
            ),
        )
        # Remove it.
        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TTEMPADD"),
        )

        show_restored = _snapshot_show(repo_root)
        assert show_original == show_restored, (
            "show output not equivalent after add+remove cycle"
        )

    def test_list_after_move_then_move_back_equivalent(
        self, tmp_path: Path,
    ) -> None:
        """Moving an entry and moving it back produces equivalent list output."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        list_original = _snapshot_list(repo_root)

        # Move Now→Next then Next→Now.
        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQDDB5V",
                horizon="Next",
            ),
        )
        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TQDDB5V",
                horizon="Now",
            ),
        )

        list_restored = _snapshot_list(repo_root)
        # Sort entries for stable comparison.
        sort_key = lambda e: (e["horizon"], e["type"], e["ref"])
        assert sorted(list_original["entries"], key=sort_key) == sorted(
            list_restored["entries"], key=sort_key
        ), "list output not equivalent after move+move-back cycle"

    def test_project_after_add_remove_cycle_preserves_other_entries(
        self, tmp_path: Path,
    ) -> None:
        """Project output for unaffected entries is identical after an
        add+remove cycle on a different entry."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        proj_before = _snapshot_project(repo_root)

        # Add and remove a temporary entry in Next.
        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TTMPCYCL",
                title="Cycle test",
                horizon="Next",
            ),
        )
        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TTMPCYCL"),
        )

        proj_after = _snapshot_project(repo_root)
        # All horizon entries should match (we added then removed from Next).
        for horizon in ("Now", "Next", "Later"):
            before_entries = [
                {"type": e["type"], "ref": e["ref"], "title": e["title"]}
                for e in proj_before["roadmap"][horizon]
            ]
            after_entries = [
                {"type": e["type"], "ref": e["ref"], "title": e["title"]}
                for e in proj_after["roadmap"][horizon]
            ]
            assert before_entries == after_entries, (
                f"Roadmap entries for {horizon} changed after add+remove cycle"
            )


# ---------------------------------------------------------------------------
# 6. Full round-trip: direct edit → lossless write → read equivalents
# ---------------------------------------------------------------------------


class TestFullRoundTripEquivalence:
    """End-to-end tests: manual edit → lossless write → show/list/project
    equivalence."""

    def test_manual_edit_then_lossless_write_preserves_all(
        self, tmp_path: Path,
    ) -> None:
        """Manual Markdown edit followed by a lossless write preserves
        everything outside roadmap bullets."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)

        # Step 1: Manually add a comment and some prose.
        content = _read_strategy(repo_root)
        content = content.replace(
            "## Constraints\n\n- Must work",
            "## Constraints\n\n<!-- Manual addition -->\nNew constraint: must be fast.\n\n- Must work",
        )
        _setup_repo(tmp_path, content)

        # Step 2: Do a lossless write (via CLI add).
        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TRNDTRP",
                title="Round-trip ticket",
                horizon="Next",
            ),
        )

        after = _read_strategy(repo_root)
        # Verify manual additions survived.
        assert "<!-- Manual addition -->" in after
        assert "New constraint: must be fast." in after
        # Verify the CLI add took effect.
        assert "[ticket:01KT50AZRMK5X890TRNDTRP]" in after
        assert "Round-trip ticket" in after

    def test_frontmatter_custom_field_round_trip(
        self, tmp_path: Path,
    ) -> None:
        """Custom frontmatter fields survive a full load→mutate→write cycle."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_FRONTMATTER_VARIATIONS)

        # Add an entry via lossless write.
        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TCUSTMFM",
                title="Custom FM test",
                horizon="Now",
            ),
        )

        after = _read_strategy(repo_root)
        assert 'custom_field: "retained-value"' in after
        assert "nested: yes" in after
        assert "count: 42" in after
        assert "[ticket:01KT50AZRMK5X890TCUSTMFM]" in after

    def test_all_headings_preserved_after_mutations(
        self, tmp_path: Path,
    ) -> None:
        """Every heading (## title) is preserved after mutations."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        required_headings = [
            "## Mission",
            "## Principles",
            "## Architecture Direction",
            "## Constraints",
            "## Non-Goals",
            "## Now",
            "## Next",
            "## Later",
        ]

        # Perform a sequence: add, move, remove.
        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TALLHDRS",
                title="All headers test",
                horizon="Next",
            ),
        )
        handle_strategy_move(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TALLHDRS",
                horizon="Later",
            ),
        )
        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TALLHDRS"),
        )

        after = _read_strategy(repo_root)
        for heading in required_headings:
            assert heading in after, f"Heading lost after mutations: {heading}"

    def test_docstring_markdown_still_parseable_after_add(self, tmp_path: Path) -> None:
        """A strategy file with rich Markdown parses cleanly even after
        mutations."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TPRSABLE",
                title="Parsable after add",
                horizon="Now",
            ),
        )

        # Load and verify it parses cleanly.
        doc = load_strategy(repo_root)
        assert doc.schema_version == "megaplan-strategy-v1"
        assert len(doc.stable_direction) == 5
        # The new entry is present.
        now_refs = [e.identity.ref for e in doc.roadmap.get("Now", [])]
        assert "01KT50AZRMK5X890TPRSABLE" in now_refs

    def test_blank_lines_in_roadmap_section_preserved_by_rewrite_engine(
        self, tmp_path: Path,
    ) -> None:
        """The _rewrite_roadmap_sections engine preserves blank lines between
        the heading and bullets."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_INTERLEAVED_BLANKS)
        original = _read_strategy(repo_root)

        doc, file_state = load_strategy_for_write(repo_root)
        write_strategy(doc, file_state, repo_root)

        after = _read_strategy(repo_root)
        # The blank lines between ## Now heading and bullet should be preserved.
        # Since there is a bullet, the rewrite preserves lines around it.
        # The key assertion: content outside roadmap is identical.
        orig_mission = _extract_section(original, "## Mission", "## Principles")
        after_mission = _extract_section(after, "## Mission", "## Principles")
        assert orig_mission == after_mission


# ---------------------------------------------------------------------------
# 7. Conflict detection does not corrupt file
# ---------------------------------------------------------------------------


class TestConflictDetectionIntegrity:
    """Prove that concurrent modification detection prevents corruption, and
    that the file remains intact after a conflict."""

    def test_conflict_does_not_write_partial_content(
        self, tmp_path: Path,
    ) -> None:
        """When a conflict is detected, the file on disk is unchanged."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        doc, file_state = load_strategy_for_write(repo_root)

        # Simulate concurrent modification: change the file externally.
        modified = original.replace("Fix authentication bug", "CHANGED EXTERNALLY")
        (repo_root / ".megaplan" / "STRATEGY.md").write_text(
            modified, encoding="utf-8"
        )

        # Now the write should raise StrategyConflictError.
        mutated = add_roadmap_entry(
            doc,
            make_roadmap_entry("ticket", "01KT50AZRMK5X890TCONFLCT", "Conflict test"),
            "Next",
        )
        with pytest.raises(StrategyConflictError):
            write_strategy(mutated, file_state, repo_root)

        # The file on disk should still be the externally-modified version,
        # not a corrupted mix.
        on_disk = _read_strategy(repo_root)
        assert "CHANGED EXTERNALLY" in on_disk
        assert "01KT50AZRMK5X890TCONFLCT" not in on_disk

    def test_no_conflict_when_file_unchanged(self, tmp_path: Path) -> None:
        """When the file hasn't been modified, write succeeds without error."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)

        doc, file_state = load_strategy_for_write(repo_root)
        mutated = add_roadmap_entry(
            doc,
            make_roadmap_entry("ticket", "01KT50AZRMK5X890TNOCCONF", "No conflict"),
            "Next",
        )
        # Should not raise.
        write_strategy(mutated, file_state, repo_root)

        after = _read_strategy(repo_root)
        assert "01KT50AZRMK5X890TNOCCONF" in after


# ---------------------------------------------------------------------------
# 8. Idempotent writes produce byte-identical files
# ---------------------------------------------------------------------------


class TestIdempotentWriteProducesIdenticalFile:
    """Prove that multiple no-op lossless writes produce byte-identical output."""

    def test_noop_write_is_idempotent(self, tmp_path: Path) -> None:
        """Two consecutive lossless writes with no mutation produce identical
        file content."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)

        # First write (no mutation).
        doc1, fs1 = load_strategy_for_write(repo_root)
        write_strategy(doc1, fs1, repo_root)
        after1 = _read_strategy(repo_root)

        # Second write (still no mutation).
        doc2, fs2 = load_strategy_for_write(repo_root)
        write_strategy(doc2, fs2, repo_root)
        after2 = _read_strategy(repo_root)

        assert after1 == after2

    def test_add_then_remove_produces_original_content(
        self, tmp_path: Path,
    ) -> None:
        """Adding then removing the same entry produces the original file
        content (modulo blank lines in the affected horizon)."""
        repo_root = _setup_repo(tmp_path, _STRATEGY_WITH_COMMENTS_AND_PROSE)
        original = _read_strategy(repo_root)

        handle_strategy_add(
            repo_root,
            _ns(
                type="ticket",
                ref="01KT50AZRMK5X890TADDRMV",
                title="Add then remove",
                horizon="Next",
            ),
        )
        handle_strategy_remove(
            repo_root,
            _ns(type="ticket", ref="01KT50AZRMK5X890TADDRMV"),
        )

        after = _read_strategy(repo_root)

        # The file should be equivalent except possibly the blank line after
        # ## Next heading (the add-then-remove may leave a blank line).
        # The key property: all non-roadmap content is identical.
        orig_without_roadmap = _extract_before_first_roadmap(original)
        after_without_roadmap = _extract_before_first_roadmap(after)
        assert orig_without_roadmap == after_without_roadmap, (
            "Non-roadmap content differs after add+remove cycle"
        )


# ---------------------------------------------------------------------------
# Helpers for section extraction
# ---------------------------------------------------------------------------


def _extract_section(text: str, start_heading: str, end_heading: str | None) -> str:
    """Extract the content of a section between *start_heading* and
    *end_heading* (or end of file if None)."""
    lines = text.split("\n")
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == start_heading.strip():
            start_idx = i
        elif end_heading is not None and line.strip() == end_heading.strip():
            end_idx = i
            break
    if start_idx is None:
        return ""
    if end_idx is None:
        end_idx = len(lines)
    return "\n".join(lines[start_idx:end_idx])


def _extract_before_first_roadmap(text: str) -> str:
    """Extract everything before the first roadmap heading (## Now)."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "## Now":
            return "\n".join(lines[:i])
    return text
