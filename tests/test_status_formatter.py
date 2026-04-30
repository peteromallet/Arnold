from __future__ import annotations

from agent_kit.resident import format_status


def test_status_formatter_in_progress_golden_string() -> None:
    assert format_status(
        {"status": "in_progress"},
        [{"tool_name": "list_images"}, {"tool_name": "send_message"}],
        "drafting",
        1_777_777_777,
    ) == "\n".join(
        [
            "Planning turn in progress.",
            "Activity: drafting",
            "Tool calls: 2",
            "Recent: list_images, send_message",
            "Updated <t:1777777777:R>",
        ]
    )


def test_status_formatter_terminal_golden_strings() -> None:
    assert (
        format_status({"status": "completed"}, [{"tool_name": "a"}], None, 10)
        == "✅ Done. 1 tool calls. <t:10:R>"
    )
    assert (
        format_status({"status": "failed", "reasoning": "boom"}, [], None, 10)
        == "❌ Failed. boom"
    )
