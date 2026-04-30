from __future__ import annotations

import pytest

from agent_kit import body
from agent_kit.templates import DEFAULT_BODY_TEMPLATE


def test_roundtrip_identity_for_markdown_fixtures() -> None:
    fixtures = [
        "plain preamble only\nwith two lines\n",
        "# Title\n\n## Goal\n\nShip the thing.\n",
        DEFAULT_BODY_TEMPLATE("Auth Flow", "Choose provider and token storage."),
        "# Title\n\n## Goal\n\nGoal text.\n\n## Context\n\n### Existing Behavior\n\nKeep this under Context.\n",
        "# Title\n\n```\n## Inside\n```\n\n## Goal\n\nOutside only.\n",
        "# Title\n\nIntro before sections.\n\n## Goal\n\nGoal text.\n",
    ]
    for fixture in fixtures:
        assert body.serialize(body.parse(fixture)) == fixture


def test_section_ops_leave_non_targeted_sections_byte_identical() -> None:
    parsed = body.parse(
        "# Title\n\n## Goal\n\nOld goal.\n\n## Context\n\nExisting context.\n\n## Deliverable\n\nA spec.\n"
    )
    changed = body.replace_section(parsed, "Context", "\nNew context.\n")

    assert changed.sections[0].raw == parsed.sections[0].raw
    assert changed.sections[2].raw == parsed.sections[2].raw
    assert changed.sections[1].raw == "## Context\n\nNew context.\n"

    appended = body.append_to_section(parsed, "Context", "\nMore.\n")
    assert appended.sections[0].raw == parsed.sections[0].raw
    assert appended.sections[2].raw == parsed.sections[2].raw

    added = body.add_section(parsed, "Open Questions", "\n- TBD\n", position="before:Deliverable")
    assert [section.name for section in added.sections] == [
        "Goal",
        "Context",
        "Open Questions",
        "Deliverable",
    ]

    renamed = body.rename_section(parsed, "Context", "Background")
    assert [section.name for section in renamed.sections] == ["Goal", "Background", "Deliverable"]
    assert renamed.sections[0].raw == parsed.sections[0].raw
    assert renamed.sections[2].raw == parsed.sections[2].raw

    removed = body.remove_section(parsed, "Context")
    assert [section.name for section in removed.sections] == ["Goal", "Deliverable"]
    assert removed.sections[0].raw == parsed.sections[0].raw
    assert removed.sections[1].raw == parsed.sections[2].raw

    reordered = body.reorder(parsed, ["Deliverable", "Goal", "Context"])
    assert [section.name for section in reordered.sections] == ["Deliverable", "Goal", "Context"]


def test_preamble_replace_controls_title_and_validation() -> None:
    parsed = body.parse("# Title\n\n## Goal\n\nGoal text.\n")

    renamed = body.replace_section(parsed, "_preamble", "# New Title\n")
    assert renamed.title == "New Title"

    missing = body.replace_section(parsed, "_preamble", "")
    assert missing.title is None
    with pytest.raises(body.BodyValidationError, match="body_missing_required_section: title"):
        body.validate_for_write(missing)


def test_lenient_parse_returns_parsed_body_and_validation_rejects_malformed_writes() -> None:
    cases = [
        "",
        "just text\n",
        "## Goal\n\ngoal\n",
        "# Title\n",
        "# Title\n\n## NotGoal\n\nx\n",
    ]
    for case in cases:
        parsed = body.parse(case)
        assert isinstance(parsed, body.ParsedBody)
        assert body.serialize(parsed) == case
        with pytest.raises(body.BodyValidationError):
            body.validate_for_write(parsed)


def test_fenced_heading_without_real_sections_is_single_preamble() -> None:
    parsed = body.parse("# Title\n\n```markdown\n## Inside\n```\n")

    assert parsed.preamble == "# Title\n\n```markdown\n## Inside\n```\n"
    assert parsed.sections == []
    assert body.serialize(parsed) == "# Title\n\n```markdown\n## Inside\n```\n"


def test_diffs_equivalent_ignores_line_endings_trailing_space_and_trailing_blank_lines_only() -> None:
    left = "--- before\r\n+++ after\r\n@@\r\n-old   \r\n+new\r\n\r\n"
    right = "--- before\n+++ after\n@@\n-old\n+new\n"

    assert body.diffs_equivalent(left, right)
    assert not body.diffs_equivalent(right, "--- before\n+++ after\n@@\n-old\n+newer\n")
