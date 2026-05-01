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
