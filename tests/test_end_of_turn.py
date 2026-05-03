from __future__ import annotations

from agent_kit.end_of_turn import (
    LOW_SECOND_OPINION_REFRAMING_SUGGESTION,
    EndOfTurnToolCall,
    ensure_reframing_suggestion,
    evaluate_end_of_turn,
)


def test_end_of_turn_reports_all_five_check_categories() -> None:
    decision = evaluate_end_of_turn(
        user_message="Change the part about scope and mark the next checklist item done.",
        response_text="",
        reply_sent=False,
        tool_calls=[],
        body_before="# Title\n\n## Scope\nOld",
        body_after="# Title\n\n## Scope\nOld",
        checklist_before=[{"id": "item_1", "label": "Scope", "status": "open"}],
        checklist_after=[{"id": "item_1", "label": "Scope", "status": "open"}],
    )

    assert {finding.category for finding in decision.findings} == {
        "no_message_sent",
        "no_tool_calls_or_progress",
        "empty_response",
        "body_unchanged_when_expected",
        "checklist_stall",
    }
    assert decision.should_error_empty_response is True
    assert decision.should_send_default_acknowledgment is False


def test_end_of_turn_default_ack_requires_substantive_tool_work() -> None:
    activity_only = evaluate_end_of_turn(
        user_message="save this preference",
        response_text=None,
        reply_sent=False,
        tool_calls=[
            EndOfTurnToolCall(
                name="set_activity",
                operation_kind="write",
                result={"description": "saving"},
            )
        ],
        body_before=None,
        body_after=None,
        checklist_before=[],
        checklist_after=[],
    )
    saved_feedback = evaluate_end_of_turn(
        user_message="save this preference",
        response_text=None,
        reply_sent=False,
        tool_calls=[
            EndOfTurnToolCall(
                name="save_feedback",
                operation_kind="write",
                result={"feedback": {"id": "feedback_1"}},
            )
        ],
        body_before=None,
        body_after=None,
        checklist_before=[],
        checklist_after=[],
    )

    assert activity_only.should_error_empty_response is True
    assert activity_only.should_send_default_acknowledgment is False
    assert saved_feedback.should_error_empty_response is False
    assert saved_feedback.should_send_default_acknowledgment is True


def test_end_of_turn_body_and_checklist_progress_clear_expected_findings() -> None:
    decision = evaluate_end_of_turn(
        user_message="Change the scope and mark the next checklist item done.",
        response_text="Done.",
        reply_sent=False,
        tool_calls=[
            EndOfTurnToolCall(
                name="edit_epic",
                operation_kind="write",
                result={"epic_id": "epic_1"},
            )
        ],
        body_before="# Title\n\n## Scope\nOld",
        body_after="# Title\n\n## Scope\nNew",
        checklist_before=[{"id": "item_1", "label": "Scope", "status": "open"}],
        checklist_after=[{"id": "item_1", "label": "Scope", "status": "done"}],
    )

    assert "body_unchanged_when_expected" not in {
        finding.category for finding in decision.findings
    }
    assert "checklist_stall" not in {finding.category for finding in decision.findings}
    assert decision.should_error_empty_response is False
    assert decision.should_send_default_acknowledgment is False


def test_low_second_opinion_score_requires_reframing_suggestion() -> None:
    tool_calls = [
        EndOfTurnToolCall(
            name="request_second_opinion",
            operation_kind="write",
            result={"score": 4, "verdict": "not ready"},
        )
    ]
    decision = evaluate_end_of_turn(
        user_message="get a second opinion",
        response_text="Score 4/10. Verdict: not ready.",
        reply_sent=False,
        tool_calls=tool_calls,
        body_before="# Title",
        body_after="# Title",
        checklist_before=[],
        checklist_after=[],
    )

    assert "second_opinion_reframe_missing" in {
        finding.category for finding in decision.findings
    }
    assert (
        ensure_reframing_suggestion("Score 4/10. Verdict: not ready.", tool_calls=tool_calls)
        == "Score 4/10. Verdict: not ready.\n\n"
        + LOW_SECOND_OPINION_REFRAMING_SUGGESTION
    )
