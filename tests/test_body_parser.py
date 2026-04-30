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


def test_outline_includes_nested_headings_line_counts_and_ignores_fenced_headings() -> None:
    parsed = body.parse(
        "# Title\n"
        "\n"
        "```markdown\n"
        "## Ignored\n"
        "```\n"
        "\n"
        "## Goal\n"
        "\n"
        "Ship it.\n"
        "\n"
        "### User Value\n"
        "Value line.\n"
        "\n"
        "#### Evidence\n"
        "Proof line.\n"
        "\n"
        "## Context\n"
        "\n"
        "Context line.\n"
    )

    outline = body.outline(parsed)

    assert outline["total_lines"] == 19
    assert [section["name"] for section in outline["sections"]] == ["Goal", "Context"]
    goal = outline["sections"][0]
    assert goal["line_start"] == 7
    assert goal["line_end"] == 16
    assert goal["line_count"] == 10
    assert goal["subheadings"] == [
        {
            "level": 3,
            "name": "User Value",
            "line_number": 11,
            "line_count": 6,
            "children": [
                {
                    "level": 4,
                    "name": "Evidence",
                    "line_number": 14,
                    "line_count": 3,
                    "children": [],
                }
            ],
        }
    ]


def test_search_returns_line_context_and_parser_section_attribution() -> None:
    parsed = body.parse(
        "# Title\n"
        "\n"
        "needle in preamble\n"
        "\n"
        "```markdown\n"
        "## Fake Section\n"
        "needle inside code\n"
        "```\n"
        "\n"
        "## Goal\n"
        "\n"
        "Goal text.\n"
        "\n"
        "### Details\n"
        "Needle in details.\n"
        "\n"
        "## Context\n"
        "No match.\n"
    )

    result = body.search(parsed, "needle", context_lines=1)

    assert result["query"] == "needle"
    assert result["results"] == [
        {
            "line_number": 3,
            "line": "needle in preamble",
            "section": "_preamble",
            "subheading_path": [],
            "context_before": [{"line_number": 2, "line": ""}],
            "context_after": [{"line_number": 4, "line": ""}],
        },
        {
            "line_number": 7,
            "line": "needle inside code",
            "section": "_preamble",
            "subheading_path": [],
            "context_before": [{"line_number": 6, "line": "## Fake Section"}],
            "context_after": [{"line_number": 8, "line": "```"}],
        },
        {
            "line_number": 15,
            "line": "Needle in details.",
            "section": "Goal",
            "subheading_path": ["Details"],
            "context_before": [{"line_number": 14, "line": "### Details"}],
            "context_after": [{"line_number": 16, "line": ""}],
        },
    ]


def test_search_empty_query_negative_context_and_tilde_fence_edges() -> None:
    parsed = body.parse(
        "# Title\n"
        "\n"
        "~~~markdown\n"
        "## Ignored\n"
        "needle inside tilde fence\n"
        "~~~\n"
        "\n"
        "## Goal\n"
        "\n"
        "Needle in goal.\n"
        "\n"
        "### Detail\n"
        "needle in detail.\n"
    )

    assert body.search(parsed, "", context_lines=2) == {"query": "", "results": []}

    result = body.search(parsed, "needle", context_lines=-4)

    assert result["results"] == [
        {
            "line_number": 5,
            "line": "needle inside tilde fence",
            "section": "_preamble",
            "subheading_path": [],
            "context_before": [],
            "context_after": [],
        },
        {
            "line_number": 10,
            "line": "Needle in goal.",
            "section": "Goal",
            "subheading_path": [],
            "context_before": [],
            "context_after": [],
        },
        {
            "line_number": 13,
            "line": "needle in detail.",
            "section": "Goal",
            "subheading_path": ["Detail"],
            "context_before": [],
            "context_after": [],
        },
    ]
