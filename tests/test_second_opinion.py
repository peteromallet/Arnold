from __future__ import annotations

import json
import sqlite3

import pytest

from agent_kit.ports import OpenAISecondOpinionResult
from agent_kit.second_opinion import parse_second_opinion
from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.second_opinion  # noqa: F401


class FakeSecondOpinionOpenAI:
    def __init__(self, raw_response: str) -> None:
        self.raw_response = raw_response
        self.calls = []

    def request_second_opinion(self, *, payload, idempotency_key: str):
        self.calls.append({"payload": payload, "idempotency_key": idempotency_key})
        return OpenAISecondOpinionResult(
            raw_response=self.raw_response,
            provider_request_id="resp_1",
            response_summary={"ok": True},
        )


def _store_with_epic():
    conn = sqlite3.connect(":memory:")
    store = SQLiteStore(conn)
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Checkout', 'Improve checkout', '# Checkout\n\n## Goal\nImprove checkout.', 'shaping')
        """
    )
    conn.commit()
    store.seed_checklist("epic_1", ["Define users", "Map states"])
    store.create_feedback(
        kind="epic_specific",
        content="Keep it concise.",
        source="explicit_save_request",
        epic_id="epic_1",
    )
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    return store, conn, turn


def test_parse_second_opinion_rejects_malformed_score() -> None:
    with pytest.raises(ValueError, match="score"):
        parse_second_opinion(json.dumps({"score": "7", "verdict": "ready", "holes": []}))


def test_parse_second_opinion_rejects_malformed_verdict_and_holes() -> None:
    with pytest.raises(ValueError, match="verdict"):
        parse_second_opinion(json.dumps({"score": 7, "verdict": "", "holes": []}))

    with pytest.raises(ValueError, match="holes"):
        parse_second_opinion(json.dumps({"score": 7, "verdict": "ready", "holes": {}}))

    with pytest.raises(ValueError, match="suggested_fix"):
        parse_second_opinion(
            json.dumps(
                {
                    "score": 7,
                    "verdict": "ready",
                    "holes": [{"gap": "Missing launch plan"}],
                }
            )
        )


def test_parse_second_opinion_accepts_text_format() -> None:
    parsed = parse_second_opinion(
        """
Score: 6/10

Strengths:
- Clear goal

Holes:
- Missing rollout: PM cannot phase the work; Add rollout milestones

Verdict: needs work
"""
    )

    assert parsed.score == 6
    assert parsed.verdict == "needs work"
    assert parsed.holes == [
        {
            "gap": "Missing rollout",
            "why_it_matters": "PM cannot phase the work",
            "suggested_fix": "Add rollout milestones",
            "severity": "medium",
        }
    ]


def test_request_second_opinion_persists_parsed_row_and_returns_proposals() -> None:
    store, conn, turn = _store_with_epic()
    raw = json.dumps(
        {
            "score": 6,
            "summary": "Useful but missing handoff detail.",
            "verdict": "needs work",
            "strengths": ["Clear problem", "Good user framing"],
            "holes": [
                {
                    "gap": "No rollout",
                    "why_it_matters": "PM cannot sequence it",
                    "suggested_fix": "Add rollout checklist",
                    "severity": "high",
                },
                {
                    "gap": "No metrics",
                    "why_it_matters": "Success is ambiguous",
                    "suggested_fix": "Define conversion metrics",
                    "severity": "medium",
                },
                {
                    "gap": "No risks",
                    "why_it_matters": "Reviewers cannot judge tradeoffs",
                    "suggested_fix": "Add risk section",
                    "severity": "medium",
                },
            ],
        }
    )
    openai_ops = FakeSecondOpinionOpenAI(raw)
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        openai_ops=openai_ops,
    )

    invocation = registry.invoke(
        "request_second_opinion",
        context,
        {
            "epic_id": "epic_1",
            "focus_areas": ["PM handoff"],
            "scoring_override": "Score readiness strictly.",
        },
    )

    result = invocation.result
    assert result["score"] == 6
    assert result["summary"] == "Useful but missing handoff detail."
    assert result["verdict"] == "needs work"
    assert len(result["holes"]) == 3
    assert [item["content"] for item in result["proposed_checklist_items"]] == [
        "Add rollout checklist",
        "Define conversion metrics",
        "Add risk section",
    ]
    assert all(
        item["source_second_opinion_id"] == result["second_opinion_id"]
        for item in result["proposed_checklist_items"]
    )
    opinions = store.list_second_opinions("epic_1")
    assert opinions[0]["id"] == result["second_opinion_id"]
    assert opinions[0]["raw_response"] == raw
    assert opinions[0]["score"] == 6
    assert opinions[0]["focus_areas"] == ["PM handoff"]
    assert openai_ops.calls[0]["payload"]["input"][0]["role"] == "system"
    user_content = json.loads(openai_ops.calls[0]["payload"]["input"][1]["content"])
    assert user_content["epic"]["body"].startswith("# Checkout")
    assert user_content["checklist"][0]["content"] == "Define users"
    external = conn.execute("SELECT provider, status FROM external_requests").fetchall()
    assert [(row["provider"], row["status"]) for row in external] == [("openai", "confirmed")]


def test_request_second_opinion_malformed_output_does_not_create_row() -> None:
    store, _conn, turn = _store_with_epic()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        openai_ops=FakeSecondOpinionOpenAI('{"score": 11, "verdict": "bad", "holes": []}'),
    )

    with pytest.raises(ValueError, match="score"):
        registry.invoke("request_second_opinion", context, {"epic_id": "epic_1"})

    assert store.list_second_opinions("epic_1") == []
