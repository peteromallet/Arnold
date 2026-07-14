from __future__ import annotations

from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentRequest,
    OpenAICompatibleAgentRunner,
)
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.request_summary import (
    REQUEST_DESCRIPTION_MAX_CHARS,
    REQUEST_SUMMARY_PREFIX,
    canonical_request_description,
    current_request_summary_line,
    source_request_fallback_line,
)
import pytest


def test_semantic_description_is_one_bounded_redacted_visible_line() -> None:
    line = current_request_summary_line(
        "Implement the contract\nwith tests and sk-abcdefghijklmnopqrstuvwxyz1234567890"
    )

    assert line.startswith("Current request: Implement the contract with tests")
    assert "sk-" not in line
    assert "\n" not in line and "\r" not in line and "\t" not in line and "\x00" not in line
    assert len(line) <= len(REQUEST_SUMMARY_PREFIX) + REQUEST_DESCRIPTION_MAX_CHARS + 1


def test_overlong_semantic_description_is_rejected_not_truncated_raw() -> None:
    with pytest.raises(ValueError, match="semantic request description exceeds"):
        canonical_request_description("x" * (REQUEST_DESCRIPTION_MAX_CHARS + 1))


def test_missing_or_ambiguous_request_never_falls_back_to_history() -> None:
    expected = "Current request: unavailable from the authoritative inbound request"

    assert current_request_summary_line(None) == expected
    assert current_request_summary_line("​\n\t") == expected
    assert current_request_summary_line(["nearby", "history"]) == expected


def test_raw_source_fallback_is_explicitly_separate_and_bounded() -> None:
    line = source_request_fallback_line("raw\nrequest " + "x" * 400)

    assert line.startswith("Current request: raw request")
    assert line.endswith("…")


def test_main_prompt_and_hot_context_messages_start_with_same_request_summary() -> None:
    request_text = "Ship the resident contract\nwith focused regressions"
    summary = current_request_summary_line(request_text)
    profile = MegaplanResidentProfile()
    system_prompt = profile.system_prompt_for(request_text).replace(
        current_request_summary_line(None), summary, 1
    )
    runner = OpenAICompatibleAgentRunner(ResidentConfig())
    messages = runner._messages(
        AgentRequest(
            conversation_id="rconv_summarycontract1",
            messages=({"role": "user", "content": request_text},),
            system_prompt=system_prompt,
            hot_context={
                "current_request": {
                    "summary_line": summary,
                    "authority": "persisted inbound records triggering this turn",
                    "source_record_ids": ["msg_summarycontract1"],
                },
                "recent_messages": [{"content": "unrelated bounded history"}],
            },
        )
    )

    assert system_prompt.splitlines()[0] == summary
    assert messages[0]["content"].splitlines()[0] == summary
    assert messages[1]["content"].splitlines()[0] == summary
