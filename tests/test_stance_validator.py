from __future__ import annotations

from arnold.pipelines.megaplan.forms.stance import validate_stance


def test_valid_stance_passes() -> None:
    assert validate_stance(
        {
            "challenge_engaged": "I engaged joke-cut-darling.",
            "angle_taken": "I chose the uglier line because it tells the truth.",
            "what_changed": "I killed the clever button.",
        }
    ) == []


def test_stance_rejects_more_than_50_words() -> None:
    violations = validate_stance(
        {
            "challenge_engaged": "I engaged poem-force-halve.",
            "angle_taken": "I chose this because " + "word " * 52,
            "what_changed": "I killed the padding.",
        }
    )
    assert any("50 words" in violation for violation in violations)


def test_stance_rejects_hedging_verb() -> None:
    violations = validate_stance(
        {
            "challenge_engaged": "I tried joke-cut-darling.",
            "angle_taken": "I chose it because it bites.",
            "what_changed": "I kept the meaner turn.",
        }
    )
    assert any("hedging verb" in violation for violation in violations)


def test_stance_rejects_third_person() -> None:
    violations = validate_stance(
        {
            "challenge_engaged": "The maker engaged joke-cut-darling.",
            "angle_taken": "The line stayed because it bites.",
            "what_changed": "The turn changed.",
        }
    )
    assert any("first person" in violation for violation in violations)


def test_stance_rejects_missing_claim_marker() -> None:
    violations = validate_stance(
        {
            "challenge_engaged": "I engaged joke-cut-darling.",
            "angle_taken": "I moved the turn toward the loud part.",
            "what_changed": "I changed the button.",
        }
    )
    assert any("claim marker" in violation for violation in violations)
