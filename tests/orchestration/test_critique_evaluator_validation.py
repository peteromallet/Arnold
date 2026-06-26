from __future__ import annotations

from arnold_pipelines.megaplan.audits.critique_evaluator import (
    validate_evaluator_verdict,
)


def _skip(check_id: str) -> dict[str, str]:
    return {"check_id": check_id, "why": "Not needed for this plan."}


def test_critique_evaluator_coerces_hard_floor_complexity() -> None:
    payload = {
        "selections": [
            {
                "check_id": "prerequisite_ordering",
                "complexity": 3,
                "complexity_justification": "Partial preconditions need review.",
                "why": "Check the dependency ordering.",
            }
        ],
        "skipped": [
            _skip("issue_hints"),
            _skip("correctness"),
            _skip("scope"),
            _skip("all_locations"),
            _skip("callers"),
            _skip("conventions"),
            _skip("verification"),
            _skip("criteria_quality"),
        ],
    }

    warnings = validate_evaluator_verdict(
        payload,
        evaluator_model="gpt-5.5",
        vendor="codex",
    )

    assert payload["selections"][0]["complexity"] == 4
    assert any("raised to the hard floor 4" in warning for warning in warnings)
