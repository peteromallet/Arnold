from arnold.pipeline import StepInvocation
from arnold.pipelines.megaplan.model_seam import ModelTier, capture_step_output
from arnold.pipelines.megaplan.schemas import SCHEMAS


def _invocation(step: str) -> StepInvocation:
    return StepInvocation(
        kind="model",
        metadata={
            "tier": ModelTier.NON_ENFORCED.value,
            "worker": "hermes",
            "model": "deepseek-v4-pro",
            "normalized_model": "deepseek-v4-pro",
            "validation_step": step,
            "compatibility_validation_step": step,
            "schema": SCHEMAS[f"{step}.json"],
        },
    )


def test_gate_normalizes_deepseek_lowercase_recommendation() -> None:
    payload = {
        "recommendation": "proceed",
        "rationale": "The plan is ready.",
        "signals_assessment": "No blocking critique flags remain.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
    }

    outcome = capture_step_output(_invocation("gate"), payload)

    assert outcome.legacy_payload["recommendation"] == "PROCEED"


def test_critique_wraps_deepseek_single_check_object() -> None:
    payload = {
        "id": "scope",
        "question": "Is the plan scoped to one worker turn?",
        "guidance": "Check for scope creep.",
        "findings": [
            {
                "detail": "Checked the listed plan phases; they remain scoped to payload contracts.",
                "flagged": False,
            }
        ],
    }

    outcome = capture_step_output(_invocation("critique"), payload)

    assert outcome.legacy_payload == {
        "checks": [
            {
                "id": "scope",
                "question": "Is the plan scoped to one worker turn?",
                "findings": [
                    {
                        "detail": "Checked the listed plan phases; they remain scoped to payload contracts.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
