"""Unit tests for legacy mode helpers (is_creative_mode / creative_form_id /
is_prose_mode).

TODO(0.24): these helpers encode the legacy mode-as-state.config.mode shape.
The 0.23 doc/creative pipelines route via state['config']['pipeline'] and
state['config']['form'] instead. The helpers (and these tests) are retained
for the legacy ``--auto-start`` planning + mode-overlay path (USER DECISION 2)
and for 0.22 plan-state compatibility; both are scheduled for removal in 0.24
alongside ``compile_pipeline_for``'s creative/joke branch.
"""
from __future__ import annotations

from megaplan._core import creative_form_id, is_creative_mode, is_prose_mode


def test_creative_mode_helper_accepts_creative_and_joke() -> None:
    assert is_creative_mode({"config": {"mode": "creative"}})
    assert is_creative_mode({"config": {"mode": "joke"}})
    assert not is_creative_mode({"config": {"mode": "code"}})


def test_creative_form_id_handles_legacy_joke_and_code() -> None:
    assert creative_form_id({"config": {"mode": "joke"}}) == "joke"
    assert creative_form_id({"config": {"mode": "creative", "form": "poem"}}) == "poem"
    assert creative_form_id({"config": {"mode": "code"}}) is None
    assert creative_form_id({"config": {"mode": "code", "form": "poem"}}) is None


def test_prose_mode_helper_includes_doc_joke_and_creative() -> None:
    assert is_prose_mode({"config": {"mode": "doc"}})
    assert is_prose_mode({"config": {"mode": "joke"}})
    assert is_prose_mode({"config": {"mode": "creative"}})
    assert not is_prose_mode({"config": {"mode": "code"}})
