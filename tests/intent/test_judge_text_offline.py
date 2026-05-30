"""Offline tests for vibecomfy.intent.judge.judge_text.

Marked intent_ci — run with: pytest -m intent_ci tests/intent

No real network calls are made; the Anthropic client is replaced with a stub
that returns canned responses.
"""

import json
import pytest

pytestmark = pytest.mark.intent_ci


class _FakeContent:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeContent(text)]


class _FakeMessages:
    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(next(self._responses))


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.messages = _FakeMessages(responses)


_PASS_RESPONSE = json.dumps({
    "pass_": True,
    "criteria": {
        "correct_node_targeted": True,
        "correct_parameter_changed": True,
        "value_semantically_matches_intent": True,
        "no_orphaned_wiring": True,
    },
    "rationale": "All criteria satisfied.",
})

_FAIL_RESPONSE = json.dumps({
    "pass_": False,
    "criteria": {
        "correct_node_targeted": True,
        "correct_parameter_changed": False,
        "value_semantically_matches_intent": False,
        "no_orphaned_wiring": True,
    },
    "rationale": "sampler_name does not control step count; value mismatch.",
})


def test_judge_text_pass_verdict():
    from vibecomfy.intent.judge import judge_text, JudgeVerdict

    client = _FakeClient([_PASS_RESPONSE])
    verdict = judge_text({"node": "pre"}, {"node": "post"}, "add more steps", client=client)

    assert isinstance(verdict, JudgeVerdict)
    assert verdict.pass_ is True
    assert all(verdict.criteria.values())


def test_judge_text_fail_verdict():
    from vibecomfy.intent.judge import judge_text, JudgeVerdict

    client = _FakeClient([_FAIL_RESPONSE])
    verdict = judge_text({"node": "pre"}, {"node": "post"}, "add more steps", client=client)

    assert isinstance(verdict, JudgeVerdict)
    assert verdict.pass_ is False
    assert verdict.criteria["correct_node_targeted"] is True
    assert verdict.criteria["correct_parameter_changed"] is False
    assert "sampler_name" in verdict.rationale


def test_judge_text_prompt_shape():
    """Verify the system prompt and user content are sent correctly."""
    from vibecomfy.intent.judge import judge_text, _SYSTEM_PROMPT

    client = _FakeClient([_PASS_RESPONSE])
    pre = {"a": 1}
    post = {"a": 2}
    intent = "test intent"
    judge_text(pre, post, intent, client=client)

    call = client.messages.calls[0]
    assert call["system"] == _SYSTEM_PROMPT
    assert call["system"].strip() != ""
    user_body = json.loads(call["messages"][0]["content"])
    assert user_body["nl_intent"] == intent
    assert user_body["pre_ir"] == pre
    assert user_body["post_ir"] == post


def test_judge_text_pass_iff_all_criteria_true():
    """pass_ must be the AND of all criteria, regardless of the raw JSON field."""
    from vibecomfy.intent.judge import judge_text

    # Model returns pass_=True but one criterion is False — our code recomputes.
    contradictory = json.dumps({
        "pass_": True,
        "criteria": {
            "correct_node_targeted": True,
            "correct_parameter_changed": True,
            "value_semantically_matches_intent": False,
            "no_orphaned_wiring": True,
        },
        "rationale": "Contradictory response.",
    })
    client = _FakeClient([contradictory])
    verdict = judge_text({}, {}, "intent", client=client)
    assert verdict.pass_ is False


def test_system_prompt_loaded_at_import():
    """_SYSTEM_PROMPT is a non-empty string loaded from the prompt file."""
    from vibecomfy.intent.judge import _SYSTEM_PROMPT

    assert isinstance(_SYSTEM_PROMPT, str)
    assert len(_SYSTEM_PROMPT) > 50
    assert "C1" in _SYSTEM_PROMPT or "correct_node_targeted" in _SYSTEM_PROMPT
