"""Regression: a pinned Claude shorthand (sonnet) must match the provider-reported
canonical id (claude-sonnet-4-6) so a deliberate execute pin does not trip the
routing-audit degradation gate; a wrong-tier substitution must still be flagged."""
from megaplan.execute.batch import _models_match, _claude_tier


def test_claude_shorthand_matches_canonical_id():
    assert _models_match("sonnet", "claude-sonnet-4-6") is True
    assert _models_match("claude:sonnet", "claude-sonnet-4-6") is True
    assert _models_match("opus", "claude-opus-4-7") is True


def test_claude_point_release_within_tier_matches():
    assert _models_match("claude-sonnet-4-5", "claude-sonnet-4-6") is True


def test_claude_wrong_tier_still_flagged():
    # opus pinned but sonnet served is a genuine degradation, NOT a match.
    assert _models_match("opus", "claude-sonnet-4-6") is False
    assert _models_match("sonnet", "claude-opus-4-7") is False


def test_cross_vendor_still_flagged():
    assert _models_match("sonnet", "gpt-5.5") is False


def test_claude_tier_normalisation():
    assert _claude_tier("sonnet") == "sonnet"
    assert _claude_tier("claude-sonnet-4-6") == "sonnet"
    assert _claude_tier("claude:opus") == "opus"
    assert _claude_tier("gpt-5.5") is None
    assert _claude_tier(None) is None
