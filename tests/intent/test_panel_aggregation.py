"""Offline tests for panel_verdict AND-aggregation.

Marked intent_ci — run with: pytest -m intent_ci tests/intent

Covers all four cells of the (text.pass_, vision.pass_) AND truth table.
No real network calls are made.
"""

import pytest

pytestmark = pytest.mark.intent_ci


def _verdict(pass_: bool) -> "JudgeVerdict":
    from vibecomfy.intent.judge import JudgeVerdict

    criteria = {
        "correct_node_targeted": pass_,
        "correct_parameter_changed": pass_,
        "value_semantically_matches_intent": pass_,
        "no_orphaned_wiring": pass_,
    }
    return JudgeVerdict(pass_=pass_, criteria=criteria, rationale="stub")


def test_panel_both_pass():
    from vibecomfy.intent.judge import panel_verdict

    pv = panel_verdict(_verdict(True), _verdict(True))
    assert pv.pass_ is True


def test_panel_text_fail_vision_pass():
    from vibecomfy.intent.judge import panel_verdict

    pv = panel_verdict(_verdict(False), _verdict(True))
    assert pv.pass_ is False


def test_panel_text_pass_vision_fail():
    from vibecomfy.intent.judge import panel_verdict

    pv = panel_verdict(_verdict(True), _verdict(False))
    assert pv.pass_ is False


def test_panel_both_fail():
    from vibecomfy.intent.judge import panel_verdict

    pv = panel_verdict(_verdict(False), _verdict(False))
    assert pv.pass_ is False


def test_panel_verdict_carries_sub_verdicts():
    from vibecomfy.intent.judge import JudgeVerdict, PanelVerdict, panel_verdict

    tv = _verdict(True)
    vv = _verdict(False)
    pv = panel_verdict(tv, vv)
    assert isinstance(pv, PanelVerdict)
    assert pv.text is tv
    assert pv.vision is vv
